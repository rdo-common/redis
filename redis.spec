%global _hardened_build 1
%global with_perftools 0

%if 0%{?fedora} >= 19 || 0%{?rhel} >= 7
# Remove redis-trib cluster management for RDO as it's not used and adds new
# requirements
%global with_redistrib 0
%else
%global with_redistrib 0
%endif

%if 0%{?fedora} >= 19 || 0%{?rhel} >= 7
%global with_systemd 1
%else
%global with_systemd 0
%endif

# Tests fail in mock, not in local build.
%global with_tests   %{?_with_tests:1}%{!?_with_tests:0}

Name:              redis
Version:           3.2.13
Release:           2%{?dist}
Summary:           A persistent key-value database
License:           BSD
URL:               http://redis.io
Source0:           http://download.redis.io/releases/%{name}-%{version}.tar.gz
Source1:           %{name}.logrotate
Source2:           %{name}-sentinel.service
Source3:           %{name}.service
Source4:           %{name}-sentinel.init
Source5:           %{name}.init
Source6:           %{name}-shutdown
Source7:           %{name}-limit-systemd
Source8:           %{name}-limit-init
# To refresh patches:
# tar xf redis-xxx.tar.gz && cd redis-xxx && git init && git add . && git commit -m "%%{version} baseline"
# git am %%{patches}
# Then refresh your patches
# git format-patch HEAD~<number of expected patches>
# Update configuration for Fedora
# https://github.com/antirez/redis/pull/3491 - man pages
Patch0001:         0001-1st-man-pageis-for-redis-cli-redis-benchmark-redis-c.patch
# https://github.com/antirez/redis/pull/3494 - symlink
Patch0002:         0002-install-redis-check-rdb-as-a-symlink-instead-of-dupl.patch
%if 0%{?with_perftools}
BuildRequires:     gperftools-devel
%else
BuildRequires:     jemalloc-devel
%endif
%if 0%{?with_tests}
BuildRequires:     procps-ng
%endif
%if 0%{?with_systemd}
BuildRequires:     systemd
%endif
%if 0%{?with_tests}
BuildRequires:     tcl
%endif
# Required for redis-shutdown
Requires:          /bin/awk
Requires:          logrotate
Requires(pre):     shadow-utils
%if 0%{?with_systemd}
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd
%else
Requires(post):    chkconfig
Requires(preun):   chkconfig
Requires(preun):   initscripts
Requires(postun):  initscripts
%endif
Provides:          bundled(hiredis)
Provides:          bundled(lua-libs)
Provides:          bundled(linenoise)

%description
Redis is an advanced key-value store. It is often referred to as a data 
structure server since keys can contain strings, hashes, lists, sets and 
sorted sets.

You can run atomic operations on these types, like appending to a string;
incrementing the value in a hash; pushing to a list; computing set 
intersection, union and difference; or getting the member with highest 
ranking in a sorted set.

In order to achieve its outstanding performance, Redis works with an 
in-memory dataset. Depending on your use case, you can persist it either 
by dumping the dataset to disk every once in a while, or by appending 
each command to a log.

Redis also supports trivial-to-setup master-slave replication, with very 
fast non-blocking first synchronization, auto-reconnection on net split 
and so forth.

Other features include Transactions, Pub/Sub, Lua scripting, Keys with a 
limited time-to-live, and configuration settings to make Redis behave like 
a cache.

You can use Redis from most programming languages also.

%if 0%{?with_redistrib}
%package           trib
Summary:           Cluster management script for Redis
BuildArch:         noarch
Requires:          ruby
Requires:          rubygem-redis

%description       trib
Redis cluster management utility providing cluster creation, node addition
and removal, status checks, resharding, rebalancing, and other operations.
%endif

%prep
%setup -q
rm -frv deps/jemalloc
%patch0001 -p1
%patch0002 -p1

# Use system jemalloc library
sed -i -e '/cd jemalloc && /d' deps/Makefile
sed -i -e 's|../deps/jemalloc/lib/libjemalloc.a|-ljemalloc -ldl|g' src/Makefile
sed -i -e 's|-I../deps/jemalloc.*|-DJEMALLOC_NO_DEMANGLE -I/usr/include/jemalloc|g' src/Makefile
# Configuration file changes and additions
sed -i -e 's|^logfile .*$|logfile /var/log/redis/redis.log|g' redis.conf
sed -i -e '$ alogfile /var/log/redis/sentinel.log' sentinel.conf
sed -i -e 's|^dir .*$|dir /var/lib/redis|g' redis.conf

%if 0%{?with_perftools}
%global malloc_flags	MALLOC=tcmalloc
%else
%global malloc_flags	MALLOC=jemalloc
%endif
%global make_flags	DEBUG="" V="echo" LDFLAGS="%{?__global_ldflags}" CFLAGS+="%{optflags} -fPIC" %{malloc_flags} INSTALL="install -p" PREFIX=%{buildroot}%{_prefix}

%build
make %{?_smp_mflags} %{make_flags} all

%install
make %{make_flags} install

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/%{name}
install -d %{buildroot}%{_localstatedir}/log/%{name}
install -d %{buildroot}%{_localstatedir}/run/%{name}

# Install logrotate file.
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install configuration files.
install -pDm640 %{name}.conf %{buildroot}%{_sysconfdir}/%{name}.conf
install -pDm640 sentinel.conf %{buildroot}%{_sysconfdir}/%{name}-sentinel.conf

# Install systemd unit files.
%if 0%{?with_systemd}
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
install -pm644 %{S:2} %{buildroot}%{_unitdir}

# Install systemd limit files (requires systemd >= 204)
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/%{name}.service.d/limit.conf
install -p -D -m 644 %{S:7} %{buildroot}%{_sysconfdir}/systemd/system/%{name}-sentinel.service.d/limit.conf
%else # install SysV service files
install -pDm755 %{S:4} %{buildroot}%{_initrddir}/%{name}-sentinel
install -pDm755 %{S:5} %{buildroot}%{_initrddir}/%{name}
install -p -D -m 644 %{S:8} %{buildroot}%{_sysconfdir}/security/limits.d/95-%{name}.conf
%endif

# Fix non-standard-executable-perm error.
chmod 755 %{buildroot}%{_bindir}/%{name}-*

# Install redis-shutdown
install -pDm755 %{S:6} %{buildroot}%{_libexecdir}/%{name}-shutdown

%if 0%{?with_redistrib}
# Install redis-trib
install -pDm755 src/%{name}-trib.rb %{buildroot}%{_bindir}/%{name}-trib
%endif

# Install man pages
man=$(dirname %{buildroot}%{_mandir})
for page in man/man?/*; do
    install -Dpm644 $page $man/$page
done
ln -s redis-server.1 %{buildroot}%{_mandir}/man1/redis-sentinel.1
ln -s redis.conf.5   %{buildroot}%{_mandir}/man5/redis-sentinel.conf.5

%check
%if 0%{?with_tests}
# https://github.com/antirez/redis/issues/1417 (for "taskset -c 1")
taskset -c 1 make test ||:
make test-sentinel ||:
%endif

%pre
getent group %{name} &> /dev/null || \
groupadd -r %{name} &> /dev/null
getent passwd %{name} &> /dev/null || \
useradd -r -g %{name} -d %{_sharedstatedir}/%{name} -s /sbin/nologin \
-c 'Redis Database Server' %{name} &> /dev/null
exit 0

%post
%if 0%{?with_systemd}
%systemd_post %{name}.service
%systemd_post %{name}-sentinel.service
%else
chkconfig --add %{name}
chkconfig --add %{name}-sentinel
%endif

%preun
%if 0%{?with_systemd}
%systemd_preun %{name}.service
%systemd_preun %{name}-sentinel.service
%else
if [ $1 -eq 0 ] ; then
    service %{name} stop &> /dev/null
    chkconfig --del %{name} &> /dev/null
    service %{name}-sentinel stop &> /dev/null
    chkconfig --del %{name}-sentinel &> /dev/null
fi
%endif

%postun
%if 0%{?with_systemd}
%systemd_postun_with_restart %{name}.service
%systemd_postun_with_restart %{name}-sentinel.service
%else
if [ "$1" -ge "1" ] ; then
    service %{name} condrestart >/dev/null 2>&1 || :
    service %{name}-sentinel condrestart >/dev/null 2>&1 || :
fi
%endif

%files
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc 00-RELEASENOTES BUGS CONTRIBUTING MANIFESTO README.md
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/%{name}.conf
%attr(0640, redis, root) %config(noreplace) %{_sysconfdir}/%{name}-sentinel.conf
%dir %attr(0750, redis, redis) %{_sharedstatedir}/%{name}
%dir %attr(0750, redis, redis) %{_localstatedir}/log/%{name}
%dir %attr(0750, redis, redis) %ghost %{_localstatedir}/run/%{name}
%if 0%{?with_redistrib}
%exclude %{_bindir}/%{name}-trib
%endif
%{_bindir}/%{name}-*
%{_libexecdir}/%{name}-*
%{_mandir}/man1/%{name}*
%{_mandir}/man5/%{name}*
%if 0%{?with_systemd}
%{_unitdir}/%{name}.service
%{_unitdir}/%{name}-sentinel.service
%dir %{_sysconfdir}/systemd/system/%{name}.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/%{name}.service.d/limit.conf
%dir %{_sysconfdir}/systemd/system/%{name}-sentinel.service.d
%config(noreplace) %{_sysconfdir}/systemd/system/%{name}-sentinel.service.d/limit.conf
%else
%{_initrddir}/%{name}
%{_initrddir}/%{name}-sentinel
%config(noreplace) %{_sysconfdir}/security/limits.d/95-%{name}.conf
%endif

%if 0%{?with_redistrib}
%files trib
%license COPYING
%{_bindir}/%{name}-trib
%endif


%changelog
* Wed Jul 29 2020 Alfredo Moralejo <amoralej@redhat.com> - 3.2.13-2
- Remove redis-trib utility in RDO build

* Fri Mar 22 2019 Carl George <carl@george.computer> - 3.2.13-1
- Latest upstream

* Fri Oct 26 2018 Nathan Scott <nathans@redhat.com> - 3.2.12-2
- Update network ordering in systemd service unit files (RHBZ #1636208)

* Fri Jul 20 2018 Nathan Scott <nathans@redhat.com> - 3.2.12-1
- Upstream 3.2.12 security fix release.
- Fixes CVE-2017-15047: Lack clusterLoadConfig input validation (RHBZ #1499153)
- Fixes CVE-2018-11218: Heap corruption in lua_cmsgpack.c (RHBZ #1591537)
- Fixes CVE-2018-11219: Integer overflow in lua_struct.c b_unpack (RHBZ #1591538)
- Fixes CVE-2018-12326: code execution via a crafted command line (RHBZ #1594294)

* Tue Sep 26 2017 Nathan Scott <nathans@redhat.com> - 3.2.11-1
- Upstream 3.2.11 bug-fix-only release
- Switch to using Type=notify for Redis systemd services (RHBZ #1172841)
- Add Provides:bundled hiredis, linenoise, lua-libs clauses (RHBZ #788500)

* Mon Aug 14 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-2
- Add redis-trib based on patch from Sebastian Saletnik.  (RHBZ #1215654)

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Mon Jul 31 2017 Nathan Scott <nathans@redhat.com> - 3.2.10-1
- Upstream 3.2.10 release
- Ensure both the redis and redis-sentinel service files set correct perms
- Dropped systemd tmpfiles source, handled directly in systemd service files

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.9-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon May 29 2017 Nathan Scott <nathans@redhat.com> - 3.2.9-1
- Upstream 3.2.9
- Add RuntimeDirectory=redis to systemd unit file (RHBZ #1454700)
- Mark rundir as %ghost since it may disappear (tmpfs - #1454700)
- Fix a shutdown failure with Unix domain sockets (RHBZ #1444988)

* Mon Feb 20 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.8-1
- Upstream 3.2.8
- bugfix for #3796 (MIGRATE could cause server crash  after socket error)

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Feb  4 2017 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.7-1
- Upstream 3.2.7 (important security fix)

* Sat Nov 05 2016 Alan Pevec <apevec AT redhat.com> - 3.2.4-2
- Install tmpfiles and /run/redis for legacy configurations

* Mon Sep 26 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.4-1
- Upstream 3.2.4
- Fix buffer overlow (TALOS-2016-0206)

* Wed Sep 14 2016 Remi Collet <remi@fedoraproject.org> - 3.2.3-2
- add missing man pages #1374577
  using patch from https://github.com/antirez/redis/pull/3491
- data and configuration should not be publicly readable #1374700
- remove /var/run/redis with systemd #1374728
- provide redis-check-rdb as a symlink to redis-server #1374736
  using patch from https://github.com/antirez/redis/pull/3494
- move redis-shutdown to libexec

* Thu Aug  4 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.2.3-1
- Upstream 3.2.3
- Security fix for CVE-2013-7458 (redis-cli history world readable)
- RHBZ#1363670 RHBZ#1363671

* Mon Feb  8 2016 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-3
- Fix redis-shutdown to handle password-protected instances shutdown

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 3.0.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Sat Dec 19 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.6-1
- Upstream 3.0.6 (RHBZ#1272281)

* Fri Oct 16 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.5-1
- Upstream 3.0.5
- Fix slave/master replication hanging forever in certain case

* Mon Sep 07 2015 Christopher Meng <rpm@cicku.me> - 3.0.4-1
- Update to 3.0.4

* Sun Aug 30 2015 Christopher Meng <rpm@cicku.me> - 3.0.3-2
- Rebuilt for jemalloc 4.0.0

* Tue Jul 21 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.3-1
- Upstream 3.0.3

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 3.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Jun 04 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.2-1
- Upstream 3.0.2 (RHBZ #1228245)
- Fix Lua sandbox escape and arbitrary code execution (RHBZ #1228331)

* Sat May 09 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.1-1
- Upstream 3.0.1 (RHBZ #1208322)

* Tue Apr 14 2015 Remi Collet <remi@fedoraproject.org> - 3.0.0-2
- rotate /var/log/redis/sentinel.log

* Thu Apr  2 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 3.0.0-1
- Upstream 3.0.0 (RHBZ #1208322)

* Thu Mar 26 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-2
- Fix redis-shutdown on multiple NIC setup (RHBZ #1201237)

* Fri Feb 27 2015 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.19-1
- Upstream 2.8.19 (RHBZ #1175232)
- Fix permissions for tmpfiles (RHBZ #1182913)
- Add limits config files
- Spec cleanups

* Fri Dec 05 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.18-1
- Upstream 2.8.18
- Rebased patches

* Sat Sep 20 2014 Remi Collet <remi@fedoraproject.org> - 2.8.17-1
- Upstream 2.8.17
- fix redis-sentinel service unit file for systemd
- fix redis-shutdown for sentinel
- also use redis-shutdown in init scripts

* Wed Sep 17 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-2
- Minor fix to redis-shutdown (from Remi Collet)

* Sat Sep 13 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.15-1
- Upstream 2.8.15 (critical bugfix for sentinel)
- Fix to sentinel systemd service and configuration (thanks Remi)
- Refresh patch management

* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-2
- Cleanup spec
- Fix shutdown for redis-{server,sentinel}
- Backport fixes from Remi Collet repository (ie: sentinel working)

* Thu Sep 11 2014 Haïkel Guémar <hguemar@fedoraproject.org> - 2.8.14-1
- Upstream 2.8.14 (RHBZ #1136287)
- Bugfix for lua scripting users (server crash)
- Refresh patches
- backport spec from EPEL7 (thanks Warren)

* Wed Jul 16 2014 Christopher Meng <rpm@cicku.me> - 2.8.13-1
- Update to 2.8.13

* Tue Jun 24 2014 Christopher Meng <rpm@cicku.me> - 2.8.12-1
- Update to 2.8.12

* Wed Jun 18 2014 Christopher Meng <rpm@cicku.me> - 2.8.11-1
- Update to 2.8.11

* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.16-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Fri Sep 06 2013 Fabian Deutsch <fabian.deutsch@gmx.de> - 2.6.16-1
- Update to 2.6.16
- Fix rhbz#973151
- Fix rhbz#656683
- Fix rhbz#977357 (Jan Vcelak <jvcelak@fedoraproject.org>)

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.13-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Tue Jul 23 2013 Peter Robinson <pbrobinson@fedoraproject.org> 2.6.13-4
- ARM has gperftools

* Wed Jun 19 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-3
- Modify jemalloc patch for s390 compatibility (Thanks sharkcz)

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-2
- Unbundle jemalloc

* Fri Jun 07 2013 Fabian Deutsch <fabiand@fedoraproject.org> - 2.6.13-1
- Add compile PIE flag (rhbz#955459)
- Update to redis 2.6.13 (rhbz#820919)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.6.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Dec 27 2012 Silas Sewell <silas@sewell.org> - 2.6.7-1
- Update to redis 2.6.7

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4.15-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-2
- Remove TODO from docs

* Sun Jul 08 2012 Silas Sewell <silas@sewell.org> - 2.4.15-1
- Update to redis 2.4.15

* Sat May 19 2012 Silas Sewell <silas@sewell.org> - 2.4.13-1
- Update to redis 2.4.13

* Sat Mar 31 2012 Silas Sewell <silas@sewell.org> - 2.4.10-1
- Update to redis 2.4.10

* Fri Feb 24 2012 Silas Sewell <silas@sewell.org> - 2.4.8-1
- Update to redis 2.4.8

* Sat Feb 04 2012 Silas Sewell <silas@sewell.org> - 2.4.7-1
- Update to redis 2.4.7

* Wed Feb 01 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-4
- Fixed a typo in the spec

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-3
- Fix .service file, to match config (Type=simple).

* Tue Jan 31 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-2
- Fix .service file, credits go to Timon.

* Thu Jan 12 2012 Fabian Deutsch <fabiand@fedoraproject.org> - 2.4.6-1
- Update to 2.4.6
- systemd unit file added
- Compiler flags changed to compile 2.4.6
- Remove doc/ and Changelog

* Sun Jul 24 2011 Silas Sewell <silas@sewell.org> - 2.2.12-1
- Update to redis 2.2.12

* Fri May 06 2011 Dan Horák <dan[at]danny.cz> - 2.2.5-2
- google-perftools exists only on selected architectures

* Sat Apr 23 2011 Silas Sewell <silas@sewell.ch> - 2.2.5-1
- Update to redis 2.2.5

* Sat Mar 26 2011 Silas Sewell <silas@sewell.ch> - 2.2.2-1
- Update to redis 2.2.2

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sun Dec 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.4-1
- Update to redis 2.0.4

* Tue Oct 19 2010 Silas Sewell <silas@sewell.ch> - 2.0.3-1
- Update to redis 2.0.3

* Fri Oct 08 2010 Silas Sewell <silas@sewell.ch> - 2.0.2-1
- Update to redis 2.0.2
- Disable checks section for el5

* Sat Sep 11 2010 Silas Sewell <silas@sewell.ch> - 2.0.1-1
- Update to redis 2.0.1

* Sat Sep 04 2010 Silas Sewell <silas@sewell.ch> - 2.0.0-1
- Update to redis 2.0.0

* Thu Sep 02 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-3
- Add Fedora build flags
- Send all scriplet output to /dev/null
- Remove debugging flags
- Add redis.conf check to init script

* Mon Aug 16 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-2
- Don't compress man pages
- Use patch to fix redis.conf

* Tue Jul 06 2010 Silas Sewell <silas@sewell.ch> - 1.2.6-1
- Initial package
