%define _python_bytecompile_skip 1
%define debug_package %{nil}

Name:               euler-copilot-framework
Version:            2.2.0
Release:            3
Summary:            Intelligent framework Engine Based On LLM (lite)
License:            MulanPSL-2.0
URL:                https://atomgit.com/openeuler/euler-copilot-framework
Source0:            %{name}-%{version}.tar.gz

Provides:   witty-framework-lite = %{version}-%{release}
Obsoletes:  witty-framework-lite < %{version}-%{release}

BuildRequires:  python3-devel
BuildRequires:  python3-pip

Requires:   python3
Requires:   python3-pip
Requires:   python3-aiofiles
Requires:   python3-asyncer
Requires:   python3-asyncpg
Requires:   python3-cryptography
Requires:   python3-fastapi
Requires:   python3-httpx-sse
Requires:   python3-jinja2
Requires:   python-jionlp
Requires:   python3-jsonschema
Requires:   python3-pandas
Requires:   python3-pgvector
Requires:   python3-pillow
Requires:   python3-python-jsonpath
Requires:   python3-magic
Requires:   python3-mcp
Requires:   python3-python-multipart
Requires:   python3-tiktoken
Requires:   python3-toml
Requires:   python3-uvicorn
Requires:   python3-xmltodict
# MCP Center
Requires:   python3-virtualenv

%description
Intelligent framework engine based on LLM that supports calling traditional
services using both low-level func_call and higher-order protocols such as MCP.
Formerly known as euler-copilot-framework.


%package -n witty-mcp-manager
Summary:    Universal MCP Host/Loader for Witty AI Assistant
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  patchelf
BuildRequires:  ccache
# uv manages the Python venv (nuitka + all deps) from witty_mcp_manager/pyproject.toml
BuildRequires:  uv
Requires:   glibc
Requires:   libstdc++
Requires(pre):  shadow-utils
Requires(pre):  pcre2

%description -n witty-mcp-manager
Universal MCP Host/Loader compiled as a single static binary via Nuitka.
Manages RPM-packaged MCP servers, legacy SSE adapters, and third-party
MCP sources with overlay configuration, session pooling, and security
sandboxing.


%prep
%setup -q -n %{name}-%{version}


%build
# witty-mcp-manager: compile to standalone deployment directory via Nuitka
pushd witty_mcp_manager
UV_INDEX_URL=https://mirrors.huaweicloud.com/repository/pypi/simple \
    bash scripts/build_nuitka.sh --mode standalone --output-dir dist
popd


%install
mkdir -p %{buildroot}%{_prefix}/lib/sysagent
cp -ar apps       %{buildroot}%{_prefix}/lib/sysagent/
cp -ar mcp_center %{buildroot}%{_prefix}/lib/sysagent/
mkdir -p %{buildroot}%{_datadir}/doc/sysagent
cp -ar docs/* %{buildroot}%{_datadir}/doc/sysagent
mkdir -p %{buildroot}%{_sharedstatedir}/sysagent
cp -ar data/* %{buildroot}%{_sharedstatedir}/sysagent/
rm -f %{buildroot}%{_sharedstatedir}/sysagent/config.example.toml
rm -f %{buildroot}%{_sharedstatedir}/sysagent/sysagent.service
install -D -m 0444 LICENSE %{buildroot}%{_datadir}/licenses/sysagent/LICENSE
install -D -m 0640 data/config.example.toml %{buildroot}%{_sysconfdir}/sysagent/config.toml
install -D -m 0644 data/sysagent.service %{buildroot}%{_sysconfdir}/systemd/system/sysagent.service
find %{buildroot}%{_prefix}/lib/sysagent -type d -exec chmod 755 {} \;
find %{buildroot}%{_prefix}/lib/sysagent -type f -exec chmod 644 {} \;

# Install standalone deployment directory, then symlink the binary to /usr/bin
install -d -m 0755 %{buildroot}%{_prefix}/lib/witty-mcp-manager
cp -ar witty_mcp_manager/dist/__main__.dist/. %{buildroot}%{_prefix}/lib/witty-mcp-manager/
chmod 0755 %{buildroot}%{_prefix}/lib/witty-mcp-manager/witty-mcp
install -d -m 0755 %{buildroot}%{_bindir}
ln -sf %{_prefix}/lib/witty-mcp-manager/witty-mcp %{buildroot}%{_bindir}/witty-mcp
install -D -m 0644 witty_mcp_manager/data/witty-mcp-manager.service \
    %{buildroot}%{_unitdir}/witty-mcp-manager.service
install -D -m 0444 LICENSE \
    %{buildroot}%{_datadir}/licenses/witty-mcp-manager/LICENSE
install -d -m 0755 %{buildroot}%{_sysconfdir}/witty
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager/overrides
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager/overrides/global
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager/overrides/users
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager/cache
install -d -m 0750 %{buildroot}%{_sharedstatedir}/witty-mcp-manager/runtime
# tmpfiles.d: creates /run/witty at boot
install -D -m 0644 /dev/stdin %{buildroot}%{_tmpfilesdir}/witty-mcp-manager.conf <<'TMPFILES'
d /run/witty 0755 witty-mcp witty-mcp -
TMPFILES


%post
packages=(
    "httpx==0.28.1"
    "ollama==0.5.3"
    "openai==2.3.0"
    "pydantic==2.11.7"
    "rich==14.2.0"
    "sqlalchemy==2.0.41"
)

mirror="https://mirrors.huaweicloud.com/repository/pypi/simple"
failed_packages=()

for package in "${packages[@]}"; do
    echo "正在安装: $package"
    if pip install --no-cache-dir "$package" -i "$mirror"; then
        echo -e "\033[0;32m$package 安装成功\033[0m"
    else
        echo -e "\033[0;31m$package 安装失败\033[0m"
        failed_packages+=("$package")
    fi
    echo "----------------------------------------"
done

%postun
if [ $1 -eq 0 ]; then
    rm -rf %{_sharedstatedir}/sysagent
    rm -rf %{_prefix}/lib/sysagent
fi


%pre -n witty-mcp-manager
getent group witty-mcp >/dev/null || groupadd -r witty-mcp
getent passwd witty-mcp >/dev/null || \
    useradd -r -g witty-mcp -s /sbin/nologin \
        -d %{_sharedstatedir}/witty-mcp-manager \
        -c "Witty MCP Manager" witty-mcp
exit 0

%post -n witty-mcp-manager
%systemd_post witty-mcp-manager.service
systemd-tmpfiles --create %{_tmpfilesdir}/witty-mcp-manager.conf 2>/dev/null || :

%preun -n witty-mcp-manager
%systemd_preun witty-mcp-manager.service

%postun -n witty-mcp-manager
%systemd_postun_with_restart witty-mcp-manager.service
if [ $1 -eq 0 ]; then
    rm -rf %{_sharedstatedir}/witty-mcp-manager
fi


%files
%defattr(-,root,root,-)
%dir %{_datadir}/doc/sysagent
%{_datadir}/doc/sysagent/*
%dir %{_prefix}/lib/sysagent
%{_prefix}/lib/sysagent/*
%dir %{_sharedstatedir}/sysagent
%{_sharedstatedir}/sysagent/*
%dir %{_datadir}/licenses/sysagent
%doc %{_datadir}/licenses/sysagent/LICENSE
%dir %{_sysconfdir}/sysagent
%config(noreplace) %{_sysconfdir}/sysagent/config.toml
%config(noreplace) %{_sysconfdir}/systemd/system/sysagent.service


%files -n witty-mcp-manager
%defattr(-,root,root,-)
%{_bindir}/witty-mcp
%dir %{_prefix}/lib/witty-mcp-manager
%{_prefix}/lib/witty-mcp-manager/*
%dir %{_datadir}/licenses/witty-mcp-manager
%license %{_datadir}/licenses/witty-mcp-manager/LICENSE
%{_unitdir}/witty-mcp-manager.service
%{_tmpfilesdir}/witty-mcp-manager.conf
%dir %{_sysconfdir}/witty
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager/overrides
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager/overrides/global
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager/overrides/users
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager/cache
%dir %attr(0750,witty-mcp,witty-mcp) %{_sharedstatedir}/witty-mcp-manager/runtime


%changelog
* Fri Mar 13 2026 Hongyu Shi <shywzt@iCloud.com> - 2.2.0-3
- Add explicit pre-install dependency on pcre2 for witty-mcp-manager account creation scriptlet
* Fri Mar 13 2026 cui-gaoleng <tangshunan1@huawei.com> - 2.2.0-2
- Update Framework for context
* Tue Feb 24 2026 Hongyu Shi <shywzt@iCloud.com> - 2.2.0-1
- Add main package alias witty-framework-lite
- Add witty-mcp-manager subpackage (Nuitka-compiled binary)
* Fri Jan 9 2026 Weitong Zhou <zhouweitong@h-partners.com> - 2.1.0-1
- Update MCPAgentExecutor
* Fri Jan 9 2026 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.1-2
- Use python3-mcp requirement
* Thu Dec 25 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.1-1
- Update SRC
* Wed Dec 24 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-6
- Change pip path
* Wed Dec 24 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-5
- Use https instead of http
* Tue Dec 23 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-4
- Update mcp_center configs
* Mon Dec 22 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-3
- Fix missing prompts
* Mon Dec 22 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-2
- Upgrade ssh command executor
* Thu Dec 4 2025 Weitong Zhou <zhouweitong@h-partners.com> - 2.0.0-1
- Add service files
- Upgrade source code to v2.0.0
* Fri Oct 24 2025 houxu <houxu5@h-partners.com> - 0.10.1-3
- Upgrade source code
* Fri Oct 17 2025 houxu <houxu5@h-partners.com> - 0.10.1-2
- Upgrade source code
* Wed Oct 15 2025 zxstty <zhaojiaqi18@huawei.com> - 0.10.1-1
- Upgrade source code
* Mon Jun 09 2025 liujiangbin <liujiangbin3@h-partners.com> - 0.9.6-1
- Package Spec generated
