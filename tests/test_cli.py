from deploy.cli import main
from deploy.errors import CreatePreflightError


def test_show_projects_as_json(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )

    exit_code = main(["--json", "--project-dir", str(project_dir), "show", "projects"])

    assert exit_code == 0
    assert '"projects"' in capsys.readouterr().out


def test_show_export_writes_json_and_fragment(tmp_path, monkeypatch) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "kris").write_text(
        '{"type":"custom","project":"kris","hostname":"kris.home.koehntopp.de","config":true}\n',
        encoding="utf-8",
    )
    (project_dir / "kris.conf").write_text(
        "<VirtualHost *:443>\n    ServerName kris.home.koehntopp.de\n</VirtualHost>\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--project-dir",
            str(project_dir),
            "show",
            "--export",
            "kris-export",
            "kris",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "kris-export").exists()
    assert (tmp_path / "kris-export.conf").exists()
    assert '"type": "custom"' in (tmp_path / "kris-export").read_text(encoding="utf-8")
    assert "ServerName kris.home.koehntopp.de" in (
        tmp_path / "kris-export.conf"
    ).read_text(encoding="utf-8")


def test_show_custom_prints_fragment_only_once(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    fragment = "<VirtualHost *:443>\n    ServerName kris.home.koehntopp.de\n</VirtualHost>\n"
    (project_dir / "kris").write_text(
        '{"type":"custom","project":"kris","hostname":"kris.home.koehntopp.de","config":true}\n',
        encoding="utf-8",
    )
    (project_dir / "kris.conf").write_text(fragment, encoding="utf-8")

    exit_code = main(["--project-dir", str(project_dir), "show", "kris"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.count("fragment:") == 1
    assert out.count("<VirtualHost *:443>") == 1


def test_create_proxy_preview_as_json(capsys) -> None:
    exit_code = main(
        [
            "--json",
            "--dry-run",
            "create",
            "proxy",
            "immich",
            "--hostname",
            "immich.home.koehntopp.de",
            "--upstream-port",
            "2283",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "apply"' in out
    assert '"mode": "dry_run"' in out
    assert '"project_type": "proxy"' in out


def test_verbose_create_reports_steps_and_summary(capsys) -> None:
    exit_code = main(
        [
            "--verbose",
            "--dry-run",
            "create",
            "proxy",
            "immich",
            "--hostname",
            "immich.home.koehntopp.de",
            "--upstream-port",
            "2283",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "verbose: start step prepare project for create" in out
    assert "verbose: done step restart httpd in " in out
    assert "verbose: summary for create" in out


def test_create_wsgi_subcommand_parses_type_specific_options(capsys) -> None:
    exit_code = main(
        [
            "--json",
            "--dry-run",
            "create",
            "wsgi",
            "webauthn",
            "--hostname",
            "webauthn.home.koehntopp.de",
            "--source-type",
            "git",
            "--source",
            "git@github.com:isotopp/webauthn-test.git",
            "--username",
            "webauthn",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "wsgi_site"' in out
    assert '"source_type": "git"' in out
    assert '"source": "git@github.com:isotopp/webauthn-test.git"' in out


def test_create_go_subcommand_parses_type_specific_options(capsys) -> None:
    exit_code = main(
        [
            "--json",
            "--dry-run",
            "create",
            "go",
            "wiki",
            "--hostname",
            "wiki.snackbag.net",
            "--source-type",
            "git",
            "--source",
            "git@github.com:snackbag/wiki.git",
            "--username",
            "wiki",
            "--upstream-port",
            "3001",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "go_site"' in out
    assert '"upstream_port": 3001' in out


def test_create_preview_skips_unsupported_host_projects(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "legacy-bot").write_text(
        '{"type":"discord_bot","project":"legacy-bot","hostname":"bot.example.invalid"}\n',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--json",
            "--dry-run",
            "--project-dir",
            str(project_dir),
            "create",
            "proxy",
            "immich",
            "--hostname",
            "immich.home.koehntopp.de",
            "--upstream-port",
            "2283",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "proxy"' in out
    assert (
        "skipping unsupported project record legacy-bot: unsupported project type: discord_bot"
        in out
    )


def test_create_static_site_does_not_uv_sync(tmp_path, capsys) -> None:
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "static",
            "keks",
            "--hostname",
            "keks.home.koehntopp.de",
            "--source-type",
            "local_git",
            "--source",
            "/home/codex/site",
            "--username",
            "keks",
        ]
    )

    assert exit_code == 0
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "sudo -u keks -- sh -lc " not in cmdlog
    assert "useradd -m -c 'Website owner keks.home.koehntopp.de' keks" in cmdlog
    assert "git config --global --add safe.directory " in cmdlog
    assert "/home/codex/site" in cmdlog
    assert "/home/codex/site/.git" in cmdlog
    assert "/home/keks/checkout" in cmdlog
    assert "/home/keks/checkout/.git" in cmdlog
    assert "git clone /home/codex/site /home/keks/checkout" in cmdlog
    assert "chmod 711 /home/keks" in cmdlog
    assert "chmod -R a+rX /home/keks/checkout" in cmdlog
    assert "uv sync" not in cmdlog


def test_create_redirect_only_writes_config_and_restarts(tmp_path, capsys) -> None:
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "redirect",
            "docs",
            "--hostname",
            "docs.home.koehntopp.de",
            "--to-hostname",
            "server.home.koehntopp.de",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "redirect_site"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "useradd " not in cmdlog
    assert "git clone " not in cmdlog
    assert "uv sync" not in cmdlog
    assert "systemctl restart httpd.service" in cmdlog
    staged_site = (
        configtest_prefix
        / apache_sites_dir.relative_to(apache_sites_dir.anchor)
        / "docs.home.koehntopp.de.conf"
    )
    assert "Use RedirectVHost docs.home.koehntopp.de server.home.koehntopp.de" in (
        staged_site.read_text(encoding="utf-8")
    )


def test_create_custom_imports_fragment_file(tmp_path, capsys) -> None:
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"
    config_file = tmp_path / "kris.conf"
    config_file.write_text(
        "<VirtualHost *:443>\n    ServerName kris.home.koehntopp.de\n</VirtualHost>\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "custom",
            "kris",
            "--hostname",
            "kris.home.koehntopp.de",
            "--config-file",
            str(config_file),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "custom"' in out
    staged_fragment = configtest_prefix / project_dir.relative_to(project_dir.anchor) / "kris.conf"
    staged_site = (
        configtest_prefix
        / apache_sites_dir.relative_to(apache_sites_dir.anchor)
        / "kris.home.koehntopp.de.conf"
    )
    assert staged_fragment.read_text(encoding="utf-8") == config_file.read_text(encoding="utf-8")
    assert "ServerName kris.home.koehntopp.de" in staged_site.read_text(encoding="utf-8")
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "useradd " not in cmdlog
    assert "git clone " not in cmdlog


def test_create_go_site_writes_systemd_unit_and_builds(tmp_path, capsys) -> None:
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "go",
            "wiki",
            "--hostname",
            "wiki.snackbag.net",
            "--source-type",
            "local_git",
            "--source",
            "/home/kris/wiki",
            "--username",
            "wiki",
            "--upstream-port",
            "3001",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "go_site"' in out
    assert '"systemd_unit_file"' in out
    staged_unit = configtest_prefix / "etc" / "systemd" / "system" / "wiki.service"
    assert staged_unit.exists()
    assert "ExecStart=/home/wiki/checkout/wiki" in staged_unit.read_text(encoding="utf-8")
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "go build -o wiki" in cmdlog
    assert "systemctl daemon-reload" in cmdlog
    assert "systemctl enable --now wiki.service" in cmdlog


def test_adopt_wsgi_writes_metadata_without_provisioning(tmp_path, capsys) -> None:
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "adopt",
            "wsgi",
            "extras",
            "--hostname",
            "extras.snackbag.net",
            "--source-type",
            "git",
            "--source",
            "git@github.com:vijfhuizen-c0derz/SnackBag-Extras.git",
            "--username",
            "extras",
            "--project-dir-name",
            "extras",
            "--home",
            "/home/extras",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "adopt"' in out
    assert '"managed_user": false' in out
    assert '"project_dir": "extras"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "useradd " not in cmdlog
    assert "git clone " not in cmdlog
    assert "uv sync" not in cmdlog


def test_delete_unmanaged_source_backed_project_warns_instead_of_userdel(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "kris").write_text(
        (
            '{"type":"static_site","project":"kris","hostname":"kris.home.koehntopp.de",'
            '"source":"git@github.com:snackbag/kris.git","source_type":"git","username":"kris-web",'
            '"project_dir":"site","home":"/home/kris-web","managed_user":false,"managed_checkout":false}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "delete",
            "kris",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "refusing to delete unmanaged user kris-web" in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "userdel -r kris-web" not in cmdlog



def test_configtest_writes_staged_files_and_command_log(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "apache-sites"
    apache_tls_config = tmp_path / "apache" / "ssldomain.conf"
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "proxy",
            "immich",
            "--hostname",
            "immich.home.koehntopp.de",
            "--upstream-port",
            "2283",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"mode": "configtest"' in out
    assert (configtest_prefix / "tmp" / "pytest-of-root").exists() is False
    assert (configtest_prefix / "cmdlog.sh").exists()
    assert "systemctl restart httpd.service" in (configtest_prefix / "cmdlog.sh").read_text(
        encoding="utf-8"
    )
    assert "systemctl --no-pager status httpd.service" in (
        configtest_prefix / "cmdlog.sh"
    ).read_text(encoding="utf-8")

    staged_project = configtest_prefix / project_dir.relative_to(project_dir.anchor) / "immich"
    staged_site = (
        configtest_prefix
        / apache_sites_dir.relative_to(apache_sites_dir.anchor)
        / "immich.home.koehntopp.de.conf"
    )
    staged_tls = configtest_prefix / apache_tls_config.relative_to(apache_tls_config.anchor)

    assert staged_project.exists()
    assert staged_site.exists()
    assert staged_tls.exists()
    assert "immich.home.koehntopp.de" in staged_tls.read_text(encoding="utf-8")


def test_restart_in_configtest_regenerates_tls_and_logs_commands(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "restart",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "restart"' in out
    staged_tls = configtest_prefix / apache_tls_config.relative_to(apache_tls_config.anchor)
    assert "plik.home.koehntopp.de" in staged_tls.read_text(encoding="utf-8")


def test_verbose_restart_reports_commands_and_summary(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--verbose",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "restart",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "verbose: start step write apache state" in out
    assert "verbose: start command systemctl restart httpd.service" in out
    assert "verbose: start step pause before second restart" in out
    assert "verbose: done command systemctl --no-pager status httpd.service rc=0 in " in out
    assert "verbose: summary for restart" in out


def test_start_in_configtest_regenerates_tls_and_logs_commands(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "start",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "start"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "systemctl start httpd.service" in cmdlog
    assert "systemctl --no-pager status httpd.service" in cmdlog
    assert "systemctl stop httpd.service" not in cmdlog
    staged_tls = configtest_prefix / apache_tls_config.relative_to(apache_tls_config.anchor)
    assert "plik.home.koehntopp.de" in staged_tls.read_text(encoding="utf-8")


def test_stop_in_configtest_logs_stop_command(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "stop",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "stop"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "systemctl stop httpd.service" in cmdlog
    assert "systemctl --no-pager status httpd.service" not in cmdlog


def test_logs_in_configtest_logs_tail_f(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "logs",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "logs"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert (
        "tail -F /var/log/httpd/error-plik.home.koehntopp.de.log "
        "/var/log/httpd/access-plik.home.koehntopp.de.log" in cmdlog
    )


def test_delete_in_configtest_logs_restart_and_stages_tls(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "grafana").write_text(
        '{"type":"proxy","project":"grafana","hostname":"grafana.home.koehntopp.de","port":3000}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "delete",
            "grafana",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "delete"' in out
    assert (configtest_prefix / "cmdlog.sh").exists()
    staged_tls = configtest_prefix / apache_tls_config.relative_to(apache_tls_config.anchor)
    assert staged_tls.exists()
    assert "grafana.home.koehntopp.de" not in staged_tls.read_text(encoding="utf-8")


def test_delete_custom_removes_fragment_file(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "kris").write_text(
        '{"type":"custom","project":"kris","hostname":"kris.home.koehntopp.de","config":true}\n',
        encoding="utf-8",
    )
    (project_dir / "kris.conf").write_text(
        "<VirtualHost *:443>\n    ServerName kris.home.koehntopp.de\n</VirtualHost>\n",
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "delete",
            "kris",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"fragment_file"' in out


def test_delete_go_site_removes_systemd_unit(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "wiki").write_text(
        (
            '{"type":"go_site","project":"wiki","hostname":"wiki.snackbag.net",'
            '"source_type":"git","source":"git@github.com:snackbag/wiki.git","username":"wiki",'
            '"projectdir":"checkout","home":"/home/wiki","port":3001}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "delete",
            "wiki",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"systemd_unit_file"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "systemctl disable --now wiki.service" in cmdlog
    assert "systemctl daemon-reload" in cmdlog


def test_delete_source_backed_in_configtest_logs_backup_and_userdel(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "keks").write_text(
        (
            '{"type":"static_site","project":"keks","hostname":"keks.home.koehntopp.de",'
            '"source_type":"local_git","source":"/home/kris/keks","username":"keks",'
            '"project_dir":"checkout","home":"/home/keks","managed_user":true,"managed_checkout":true}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "delete",
            "keks",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"backup_archive": "/home/keks.tgz"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "rm -f /home/keks.tgz" in cmdlog
    assert "tar --exclude /home/keks/checkout -czf /home/keks.tgz /home/keks" in cmdlog
    assert "userdel -r keks" in cmdlog


def test_delete_force_in_configtest_reports_force(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "keks").write_text(
        (
            '{"type":"static_site","project":"keks","hostname":"keks.home.koehntopp.de",'
            '"source_type":"local_git","source":"/home/kris/keks","username":"keks",'
            '"project_dir":"checkout","home":"/home/keks","managed_user":true,"managed_checkout":true}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "delete",
            "--force",
            "keks",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"force": true' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "systemctl restart httpd.service" in cmdlog
    assert "systemctl --no-pager status httpd.service" in cmdlog
    assert "userdel -r keks" in cmdlog


def test_delete_force_missing_project_is_noop(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()

    exit_code = main(
        [
            "--json",
            "--dry-run",
            "--project-dir",
            str(project_dir),
            "delete",
            "--force",
            "keks",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"force": true' in out
    assert '"project": null' in out
    assert "project already absent: keks" in out


def test_restart_warns_for_manual_site_domains(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    apache_sites_dir = tmp_path / "sites"
    apache_sites_dir.mkdir()
    (apache_sites_dir / "openwebui.home.koehntopp.de.conf").write_text(
        "# manual site\n",
        encoding="utf-8",
    )
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "restart",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"warnings"' in out
    assert "manual site domain included in ssldomain.conf: openwebui.home.koehntopp.de" in out
    staged_tls = configtest_prefix / apache_tls_config.relative_to(apache_tls_config.anchor)
    assert "openwebui.home.koehntopp.de" in staged_tls.read_text(encoding="utf-8")


def test_update_in_configtest_logs_git_commands_for_wsgi(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "webauthn").write_text(
        (
            '{"type":"wsgi_site","project":"webauthn","hostname":"webauthn.home.koehntopp.de",'
            '"source_type":"git","source":"git@github.com:isotopp/webauthn-test.git","username":"webauthn",'
            '"projectdir":"webauthn","home":"/home/webauthn"}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "update",
            "webauthn",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"phase": "update"' in out
    assert '"supported": true' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "sudo -u webauthn -- git config --global --add safe.directory" not in cmdlog
    assert "sudo -u webauthn -- sh -lc " in cmdlog
    assert "cd /home/webauthn/webauthn && exec git reset --hard" in cmdlog
    assert "cd /home/webauthn/webauthn && exec git pull --rebase" in cmdlog
    assert "cd /home/webauthn/webauthn && exec " in cmdlog
    assert " sync'" in cmdlog


def test_update_local_git_uses_env_inside_sudo(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "keks").write_text(
        (
            '{"type":"static_site","project":"keks","hostname":"keks.home.koehntopp.de",'
            '"source_type":"local_git","source":"/home/kris/keks","username":"keks",'
            '"projectdir":"checkout","home":"/home/keks"}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "update",
            "keks",
        ]
    )

    assert exit_code == 0
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "git config --global --add safe.directory " in cmdlog
    assert "/home/kris/keks" in cmdlog
    assert "/home/kris/keks/.git" in cmdlog
    assert "/home/keks/checkout" in cmdlog
    assert "/home/keks/checkout/.git" in cmdlog
    assert "cd /home/keks/checkout && exec git reset --hard" not in cmdlog
    assert "cd /home/keks/checkout && exec git pull --rebase" not in cmdlog
    assert "cd /home/keks/checkout" in cmdlog
    assert "\ngit pull --rebase\n" in cmdlog
    assert "chmod 711 /home/keks" in cmdlog
    assert "chmod -R a+rX /home/keks/checkout" in cmdlog
    assert "uv sync" not in cmdlog


def test_update_skips_proxy_project(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "plik").write_text(
        '{"type":"proxy","project":"plik","hostname":"plik.home.koehntopp.de","port":8084}\n',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--json",
            "--dry-run",
            "--project-dir",
            str(project_dir),
            "update",
            "plik",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"supported": false' in out
    assert "source-backed update workflow" in out


def test_update_go_site_builds_and_restarts_service(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "wiki").write_text(
        (
            '{"type":"go_site","project":"wiki","hostname":"wiki.snackbag.net",'
            '"source_type":"local_git","source":"/home/kris/wiki","username":"wiki",'
            '"projectdir":"checkout","home":"/home/wiki","port":3001}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "update",
            "wiki",
        ]
    )

    assert exit_code == 0
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "git reset --hard" in cmdlog
    assert "git pull --rebase" in cmdlog
    assert "cd /home/wiki/checkout && exec go build -o wiki" in cmdlog
    assert "systemctl restart wiki.service" in cmdlog


def test_create_wsgi_local_git_uses_checkout_and_updater(tmp_path, capsys) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text(
        (
            '[project]\nname = "demo"\nversion = "0.1.0"\n'
            '[tool.deploy]\nupdater = ["uv", "run", "python", "-m", "demo.update"]\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"
    project_dir = tmp_path / "projects"
    apache_sites_dir = tmp_path / "sites"
    apache_tls_config = tmp_path / "conf.d" / "ssldomain.conf"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "--apache-sites-dir",
            str(apache_sites_dir),
            "--apache-tls-config",
            str(apache_tls_config),
            "create",
            "wsgi",
            "demo",
            "--hostname",
            "demo.home.koehntopp.de",
            "--source-type",
            "local_git",
            "--source",
            str(source_dir),
            "--username",
            "demo",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_dir": "checkout"' in out
    assert '"source_type": "local_git"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert "useradd -m -c 'Website owner demo.home.koehntopp.de' demo" in cmdlog
    assert "git config --global --add safe.directory " in cmdlog
    assert str(source_dir.resolve()) in cmdlog
    assert str(source_dir.resolve() / ".git") in cmdlog
    assert "/home/demo/checkout" in cmdlog
    assert "/home/demo/checkout/.git" in cmdlog
    assert f"git clone {source_dir.resolve()} /home/demo/checkout" in cmdlog
    assert "sudo -u demo -- sh -lc 'cd /home/demo/checkout && exec " in cmdlog
    assert " sync'" in cmdlog
    assert "sudo -u demo -- sh -lc 'cd /home/demo/checkout && exec ln -sfn .venv venv'" in cmdlog
    assert "cd /home/demo/checkout && exec " in cmdlog
    assert " run python -m demo.update'" in cmdlog


def test_create_rejects_existing_user(tmp_path) -> None:
    try:
        main(
            [
                "create",
                "wsgi",
                "demo",
                "--hostname",
                "demo.home.koehntopp.de",
                "--source-type",
                "git",
                "--source",
                "git@github.com:isotopp/demo.git",
                "--username",
                "root",
            ]
        )
    except CreatePreflightError as exc:
        assert "user already exists" in str(exc)
    else:
        raise AssertionError("expected CreatePreflightError")


def test_logs_go_site_uses_apache_and_journalctl(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "wiki").write_text(
        (
            '{"type":"go_site","project":"wiki","hostname":"wiki.snackbag.net",'
            '"source_type":"git","source":"git@github.com:snackbag/wiki.git","username":"wiki",'
            '"projectdir":"checkout","home":"/home/wiki","port":3001}\n'
        ),
        encoding="utf-8",
    )
    configtest_prefix = tmp_path / "staging"

    exit_code = main(
        [
            "--json",
            "--configtest",
            str(configtest_prefix),
            "--project-dir",
            str(project_dir),
            "logs",
            "wiki",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"service_unit": "wiki.service"' in out
    cmdlog = (configtest_prefix / "cmdlog.sh").read_text(encoding="utf-8")
    assert (
        "tail -F /var/log/httpd/error-wiki.snackbag.net.log "
        "/var/log/httpd/access-wiki.snackbag.net.log" in cmdlog
    )
    assert "journalctl --no-pager -u wiki.service -f" in cmdlog
