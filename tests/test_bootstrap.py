from deploy.apache_bootstrap import run_bootstrap
from deploy.runtime import ExecutionContext, RunMode
from deploy.settings import DeployPaths, DeploySettings


def make_settings(tmp_path):
    httpd_root = tmp_path / "etc" / "httpd"
    httpd_conf = httpd_root / "conf" / "httpd.conf"
    httpd_conf.parent.mkdir(parents=True, exist_ok=True)
    httpd_conf.write_text(
        (
            'ServerRoot "/etc/httpd"\n'
            "IncludeOptional conf.d/*.conf\n"
            "<IfModule status_module>\n"
            '    <Location "/server-status">\n'
            "        SetHandler server-status\n"
            "        Require ip 1.2.3.4 127.0.0.1 192.168.0.0/16\n"
            "    </Location>\n"
            "</IfModule>\n"
            "<IfModule info_module>\n"
            '    <Location "/server-info">\n'
            "        SetHandler server-info\n"
            "        Require ip 1.2.3.4 127.0.0.1 192.168.0.0/16\n"
            "    </Location>\n"
            "</IfModule>\n"
        ),
        encoding="utf-8",
    )
    return DeploySettings(
        paths=DeployPaths(
            project_dir=tmp_path / "etc" / "projects",
            httpd_conf=httpd_conf,
            apache_sites_dir=httpd_root / "conf.sites.d",
            apache_tls_config=httpd_root / "conf.d" / "ssldomain.conf",
            apache_macros_config=httpd_root / "conf.d" / "macros.conf",
            ssl_conf=httpd_root / "conf.d" / "ssl.conf",
            brotli_module_conf=httpd_root / "conf.modules.d" / "00-brotli.conf",
            dav_module_conf=httpd_root / "conf.modules.d" / "00-dav.conf",
            cgi_module_conf=httpd_root / "conf.modules.d" / "01-cgi.conf",
            httpd_logrotate=tmp_path / "etc" / "logrotate.d" / "httpd",
            machine_fqdn="server.home.koehntopp.de",
        )
    )


def seed_existing_apache_state(settings: DeploySettings) -> None:
    settings.paths.apache_tls_config.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.apache_tls_config.write_text(
        (
            "Servername server.home.koehntopp.de\n"
            "MDCertificateAgreement accepted\n"
            "MDPrivateKeys RSA 4096\n"
            "MDomain server.home.koehntopp.de grafana.home.koehntopp.de\n"
        ),
        encoding="utf-8",
    )
    settings.paths.apache_sites_dir.mkdir(parents=True, exist_ok=True)
    (settings.paths.apache_sites_dir / "webauthn.home.koehntopp.de.conf").write_text(
        "# generated\n",
        encoding="utf-8",
    )


def test_bootstrap_default_writes_added_files_and_include(tmp_path) -> None:
    settings = make_settings(tmp_path)
    result = run_bootstrap(
        settings=settings,
        context=ExecutionContext(mode=RunMode.CONFIGTEST, configtest_prefix=tmp_path / "stage"),
        mode_all=False,
        mode_ip_only=False,
    )

    staged_httpd_conf = tmp_path / "stage" / "tmp" / "pytest-of-kris"
    assert result.external_ip is None
    assert "macros_conf" in result.written
    assert "ssldomain_conf" in result.written
    assert "httpd_conf" in result.written
    assert (
        tmp_path
        / "stage"
        / settings.paths.apache_macros_config.relative_to(
            settings.paths.apache_macros_config.anchor
        )
    ).exists()
    httpd_conf = (
        tmp_path / "stage" / settings.paths.httpd_conf.relative_to(settings.paths.httpd_conf.anchor)
    ).read_text(encoding="utf-8")
    assert settings.paths.apache_sites_include in httpd_conf


def test_bootstrap_ip_only_updates_ip_lines(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    monkeypatch.setattr("deploy.apache_bootstrap.fetch_external_ip", lambda: "8.8.8.8")

    result = run_bootstrap(
        settings=settings,
        context=ExecutionContext(mode=RunMode.CONFIGTEST, configtest_prefix=tmp_path / "stage"),
        mode_all=False,
        mode_ip_only=True,
    )

    assert result.external_ip == "8.8.8.8"
    staged_httpd = (
        tmp_path / "stage" / settings.paths.httpd_conf.relative_to(settings.paths.httpd_conf.anchor)
    ).read_text(encoding="utf-8")
    assert "Require ip 8.8.8.8 127.0.0.1 192.168.0.0/16" in staged_httpd


def test_bootstrap_all_logs_rotation_and_writes_managed_files(tmp_path, monkeypatch) -> None:
    settings = make_settings(tmp_path)
    seed_existing_apache_state(settings)
    monkeypatch.setattr("deploy.apache_bootstrap.fetch_external_ip", lambda: "8.8.4.4")

    result = run_bootstrap(
        settings=settings,
        context=ExecutionContext(mode=RunMode.CONFIGTEST, configtest_prefix=tmp_path / "stage"),
        mode_all=True,
        mode_ip_only=False,
    )

    assert result.external_ip == "8.8.4.4"
    cmdlog = (tmp_path / "stage" / "cmdlog.sh").read_text(encoding="utf-8")
    httpd_root = settings.paths.httpd_conf.parent.parent
    httpd_backup = httpd_root.with_name("httpd.bak")
    assert f"rm -rf {httpd_backup}" in cmdlog
    assert f"mv {httpd_root} {httpd_backup}" in cmdlog
    assert f"cp -a {httpd_backup} {httpd_root}" in cmdlog
    staged_ssl = (
        tmp_path / "stage" / settings.paths.ssl_conf.relative_to(settings.paths.ssl_conf.anchor)
    ).read_text(encoding="utf-8")
    assert "Listen 443 https" in staged_ssl
    staged_ssldomain = (
        tmp_path
        / "stage"
        / settings.paths.apache_tls_config.relative_to(settings.paths.apache_tls_config.anchor)
    ).read_text(encoding="utf-8")
    assert "grafana.home.koehntopp.de" in staged_ssldomain
    assert "webauthn.home.koehntopp.de" in staged_ssldomain
