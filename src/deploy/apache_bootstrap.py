from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from .apache import render_ssldomain_config, site_hostnames_from_dir
from .fs import FileSystem
from .runner import CommandRunner
from .runtime import ExecutionContext, RunMode
from .settings import DeploySettings

SERVER_ADMIN = "kristian.koehntopp@gmail.com"
COMBINEDIO_LOG_FORMAT = '      LogFormat "%h %l %u %t \\"%r\\" %>s %b \\"%{{Referer}}i\\" \\"%{{User-Agent}}i\\" %I %O" combinedio'  # noqa: E501

HTTPD_CONF_TEMPLATE = """ServerRoot "/etc/httpd"
ServerTokens Prod

Listen 80
# Liste 443 in ssl.conf elsewhere

Include conf.modules.d/*.conf

User apache
Group apache

ServerAdmin {server_admin}

<Directory />
    AllowOverride none
    Require all denied
</Directory>

DocumentRoot "/var/www/html"

<Directory "/var/www">
    AllowOverride None
    # Allow open access:
    Require all granted
</Directory>

<Directory "/var/www/html">
    Options Indexes FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>

<IfModule dir_module>
    DirectoryIndex index.html
</IfModule>

<Files ".ht*">
    Require all denied
</Files>

ErrorLog "/var/log/httpd/error.log"
LogLevel warn

<IfModule log_config_module>
    LogFormat "%h %l %u %t \\"%r\\" %>s %b \\"%{{Referer}}i\\" \\"%{{User-Agent}}i\\"" combined
    LogFormat "%h %l %u %t \\"%r\\" %>s %b" common

    <IfModule logio_module>
__COMBINEDIO_LOG_FORMAT__
    </IfModule>

    CustomLog "/var/log/httpd/access.log" combined
</IfModule>

<Directory "/var/www/cgi-bin">
    AllowOverride None
    Options None
    Require all granted
</Directory>

<IfModule mime_module>
    TypesConfig /etc/mime.types
    AddType application/x-compress .Z
    AddType application/x-gzip .gz .tgz
    AddType text/html .shtml
    AddOutputFilter INCLUDES .shtml
</IfModule>

AddDefaultCharset UTF-8

<IfModule mime_magic_module>
    MIMEMagicFile conf/magic
</IfModule>

<IfModule status_module>
    <Location "/server-status">
        SetHandler server-status
        Require ip {server_status_ips}
    </Location>
</IfModule>

<IfModule info_module>
    <Location "/server-info">
        SetHandler server-info
        Require ip {server_status_ips}
    </Location>
</IfModule>

EnableSendfile on

IncludeOptional conf.d/*.conf
IncludeOptional conf.sites.d/*.conf
"""

SSL_CONF_CONTENT = """Listen 443 https

SSLPassPhraseDialog exec:/usr/libexec/httpd-ssl-pass-dialog

SSLSessionCache         shmcb:/run/httpd/sslcache(512000)
SSLSessionCacheTimeout  300

SSLCryptoDevice builtin


<VirtualHost _default_:443>
\t#ErrorLog logs/ssl_error_log
\t#TransferLog logs/ssl_access_log
\t#LogLevel warn
\t
\tSSLEngine on
\tSSLHonorCipherOrder on
\t
\tSSLCipherSuite PROFILE=SYSTEM
\tSSLProxyCipherSuite PROFILE=SYSTEM
\t#SSLCertificateFile /etc/pki/tls/certs/localhost.crt
\t#SSLCertificateKeyFile /etc/pki/tls/private/localhost.key
\t
\t#<FilesMatch "\\.(cgi|shtml|phtml|php)$">
\t#    SSLOptions +StdEnvVars
\t#</FilesMatch>
\t#<Directory "/var/www/cgi-bin">
\t#    SSLOptions +StdEnvVars
\t#</Directory>
\t#
\tBrowserMatch "MSIE [2-5]" \\
\t         nokeepalive ssl-unclean-shutdown \\
\t         downgrade-1.0 force-response-1.0
\t
\t#CustomLog logs/ssl_request_log \\
\t#          "%t %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \\"%r\\" %b"
\t
</VirtualHost>
"""

BROTLI_CONF_CONTENT = """# LoadModule brotli_module modules/mod_brotli.so
# 
"""

DAV_CONF_CONTENT = """# LoadModule dav_module modules/mod_dav.so
# LoadModule dav_fs_module modules/mod_dav_fs.so
# LoadModule dav_lock_module modules/mod_dav_lock.so
# 
"""

CGI_CONF_CONTENT = """# This configuration file loads a CGI module appropriate to the MPM
# which has been configured in 00-mpm.conf.  mod_cgid should be used
# with a threaded MPM; mod_cgi with the prefork MPM.
# 
# <IfModule !mpm_prefork_module>
#    LoadModule cgid_module modules/mod_cgid.so
# </IfModule>
# <IfModule mpm_prefork_module>
#    LoadModule cgi_module modules/mod_cgi.so
# </IfModule>
# 
# 
"""

HTTPD_LOGROTATE_CONTENT = """# Note that logs are not compressed unless "compress" is configured,
# which can be done either here or globally in /etc/logrotate.conf.
/var/log/httpd/*.log {
    compress
    create 0644 root root
    daily
    dateext
    delaycompress
    missingok
    olddir /var/log/httpd/OLD
    rotate 30
    sharedscripts
    postrotate
        /bin/systemctl reload httpd.service > /dev/null 2>/dev/null || true
    endscript
}
"""


def macros_conf_content() -> str:
    return """<Macro VHost $host>
    <VirtualHost *:80>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot /var/www/$host
        <Directory /var/www/$host>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>
        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        RewriteEngine On
        RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot /var/www/$host
        <Directory /var/www/$host>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>

        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        SSLEngine On
    </VirtualHost>
</Macro>

<Macro StaticVHost $host $docroot>
    <VirtualHost *:80>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot $docroot
        <Directory $docroot>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>
        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        RewriteEngine On
        RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot $docroot
        <Directory $docroot>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>

        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        SSLEngine On
    </VirtualHost>
</Macro>

<Macro ProxyVHost $host $toport>
    <VirtualHost *:80>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        RewriteEngine On
        RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        SSLEngine on
        ProxyPreserveHost On

\t# http proxy
        ProxyPass "/" "http://127.0.0.1:$toport/" nocanon
        ProxyPassReverse "/" "http://127.0.0.1:$toport/"

\t# Websockets Proxy
\tProxyPass "/ws/" "ws://127.0.0.1:$toport/ws/"
\tProxyPassReverse "/ws/" "ws://127.0.0.1:$toport/ws/"

        RequestHeader set X-Forwarded-Proto %{REQUEST_SCHEME}s
        RequestHeader set X-Forwarded-For %{REMOTE_ADDR}s
        RequestHeader set X-Real-IP %{REMOTE_ADDR}s
        AllowEncodedSlashes NoDecode

\t# Timeout Settings
\tTimeout 600
\tProxyTimeout 600
    </VirtualHost>
</Macro>

<Macro PyApp $host $title $appdir $unixuser $unixgroup>
    <VirtualHost *:80>
        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot /var/www/$host
        <Directory /var/www/$host>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>
        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        RewriteEngine On
        RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
        ProxyPreserveHost On

        ServerName $host
        ServerAdmin kristian.koehntopp@gmail.com

        DocumentRoot /var/www/$host
        <Directory /var/www/$host>
            Options Indexes FollowSymLinks
            AllowOverride None
            Require all granted
        </Directory>

        Alias /static $appdir/$title/static

        WSGIDaemonProcess $title processes=5 threads=2 user=$unixuser group=$unixgroup \\
            display-name=%{GROUP} maximum-requests=100 python-home=$appdir/venv \\
            python-path=$appdir/src
        WSGIProcessGroup $title
        DocumentRoot $appdir
        WSGIScriptAlias / $appdir/app.wsgi
        <Directory $appdir>
            Options Indexes FollowSymlinks
            AllowOverride None
            Require all granted
        </Directory>

        ErrorLog /var/log/httpd/error-$host.log
        CustomLog /var/log/httpd/access-$host.log combined

        SSLEngine On
    </VirtualHost>
</Macro>

<Macro RedirectVHost $fromdomain $todomain>
    <VirtualHost *:80>
        ServerName $fromdomain
        ErrorLog /var/log/httpd/error-$fromdomain.log
        CustomLog /var/log/httpd/access-$fromdomain.log combined
        RewriteEngine On
        RewriteCond %{HTTP_HOST} ^$fromdomain$ [NC]
        RewriteRule ^/(.*)$ http://$todomain/$1 [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
        ServerName $fromdomain
        ErrorLog /var/log/httpd/error-$fromdomain.log
        CustomLog /var/log/httpd/access-$fromdomain.log combined
        SSLEngine On
        RewriteEngine On
        RewriteCond %{HTTP_HOST} ^$fromdomain$ [NC]
        RewriteRule ^/(.*)$ https://$todomain/$1 [R=301,L]
    </VirtualHost>
</Macro>
"""


def fetch_external_ip() -> str:
    response = httpx.get("https://api.ipify.org", timeout=5.0)
    response.raise_for_status()
    return response.text.strip()


def ensure_include(text: str, include_line: str) -> str:
    if include_line in text:
        return text
    text = text.rstrip() + "\n"
    return f"{text}{include_line}\n"


def render_status_ip_ranges(external_ip: str, additional_ips: list[str]) -> str:
    seen: set[str] = set()
    values: list[str] = []
    for value in [external_ip, *additional_ips, "127.0.0.1", "192.168.0.0/16"]:
        if value not in seen:
            seen.add(value)
            values.append(value)
    return " ".join(values)


def update_status_ip_restrictions(text: str, external_ip: str, additional_ips: list[str]) -> str:
    replacement = f"        Require ip {render_status_ip_ranges(external_ip, additional_ips)}"
    text = re.sub(r'(^\s*Require ip .*$)', replacement, text, count=1, flags=re.MULTILINE)
    text = re.sub(r'(^\s*Require ip .*$)', replacement, text, count=1, flags=re.MULTILINE)
    return text


def existing_ssldomain_hostnames(path: Path, fqdn: str) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("MDomain "):
            continue
        hostnames = line.removeprefix("MDomain ").split()
        return [hostname for hostname in hostnames if hostname != fqdn]
    return []

def merge_hostnames(required: list[str], existing: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for hostname in [*required, *existing]:
        if hostname not in seen:
            seen.add(hostname)
            merged.append(hostname)
    return merged


@dataclass(frozen=True)
class BootstrapResult:
    written: dict[str, Path]
    external_ip: str | None = None


def bootstrap_added_files(settings: DeploySettings, fs: FileSystem) -> dict[str, Path]:
    paths = settings.paths
    fs.mkdir(paths.apache_sites_dir)
    existing_hostnames = site_hostnames_from_dir(paths.apache_sites_dir)
    written = {
        "macros_conf": fs.write_text(paths.apache_macros_config, macros_conf_content()),
        "ssldomain_conf": fs.write_text(
            paths.apache_tls_config,
            render_ssldomain_config(existing_hostnames, fqdn=paths.machine_fqdn),
        ),
    }
    httpd_text = paths.httpd_conf.read_text(encoding="utf-8")
    written["httpd_conf"] = fs.write_text(
        paths.httpd_conf,
        ensure_include(httpd_text, paths.apache_sites_include),
    )
    return written


def bootstrap_ip_only(
    settings: DeploySettings,
    fs: FileSystem,
    external_ip: str,
    additional_ips: list[str],
) -> dict[str, Path]:
    httpd_text = settings.paths.httpd_conf.read_text(encoding="utf-8")
    updated = update_status_ip_restrictions(httpd_text, external_ip, additional_ips)
    return {"httpd_conf": fs.write_text(settings.paths.httpd_conf, updated)}


def render_httpd_conf(external_ip: str, additional_ips: list[str]) -> str:
    return HTTPD_CONF_TEMPLATE.replace(
        "__COMBINEDIO_LOG_FORMAT__",
        COMBINEDIO_LOG_FORMAT,
    ).format(
        server_admin=SERVER_ADMIN,
        server_status_ips=render_status_ip_ranges(external_ip, additional_ips),
    )


def bootstrap_all(
    settings: DeploySettings,
    fs: FileSystem,
    runner: CommandRunner,
    external_ip: str,
    additional_ips: list[str],
) -> dict[str, Path]:
    paths = settings.paths
    httpd_root = paths.httpd_conf.parent.parent
    httpd_backup = httpd_root.with_name("httpd.bak")

    runner.run(["rm", "-rf", str(httpd_backup)])
    runner.run(["mv", str(httpd_root), str(httpd_backup)])
    runner.run(["cp", "-a", str(httpd_backup), str(httpd_root)])

    fs.mkdir(paths.apache_sites_dir)
    hostname_source_root = httpd_backup
    if fs.context.mode is not RunMode.LIVE:
        # In configtest/dry-run the rotation is logged, not executed, so the
        # current httpd tree remains the only readable source of live state.
        hostname_source_root = httpd_root
    existing_hostnames = site_hostnames_from_dir(hostname_source_root / "conf.sites.d")
    written: dict[str, Path] = {}
    written["httpd_conf"] = fs.write_text(
        paths.httpd_conf,
        render_httpd_conf(external_ip, additional_ips),
    )
    written["ssl_conf"] = fs.write_text(paths.ssl_conf, SSL_CONF_CONTENT)
    written["brotli_module_conf"] = fs.write_text(paths.brotli_module_conf, BROTLI_CONF_CONTENT)
    written["dav_module_conf"] = fs.write_text(paths.dav_module_conf, DAV_CONF_CONTENT)
    written["cgi_module_conf"] = fs.write_text(paths.cgi_module_conf, CGI_CONF_CONTENT)
    written["httpd_logrotate"] = fs.write_text(paths.httpd_logrotate, HTTPD_LOGROTATE_CONTENT)
    written["macros_conf"] = fs.write_text(paths.apache_macros_config, macros_conf_content())
    written["ssldomain_conf"] = fs.write_text(
        paths.apache_tls_config,
        render_ssldomain_config(existing_hostnames, fqdn=paths.machine_fqdn),
    )
    return written


def run_bootstrap(
    *,
    settings: DeploySettings,
    context: ExecutionContext,
    mode_all: bool,
    mode_ip_only: bool,
    external_ip: str | None = None,
    additional_ips: list[str] | None = None,
) -> BootstrapResult:
    fs = FileSystem(context)
    runner = CommandRunner(context)
    discovered_ip = external_ip
    extra_ips = additional_ips or []

    if mode_all or mode_ip_only:
        discovered_ip = discovered_ip or fetch_external_ip()

    if mode_all:
        assert discovered_ip is not None
        written = bootstrap_all(settings, fs, runner, discovered_ip, extra_ips)
    elif mode_ip_only:
        assert discovered_ip is not None
        written = bootstrap_ip_only(settings, fs, discovered_ip, extra_ips)
    else:
        written = bootstrap_added_files(settings, fs)

    return BootstrapResult(written=written, external_ip=discovered_ip)
