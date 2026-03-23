from deploy.cli import main


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


def test_create_wsgi_subcommand_parses_type_specific_options(capsys) -> None:
    exit_code = main(
        [
            "--json",
            "--dry-run",
            "create",
            "wsgi-site",
            "webauthn",
            "--hostname",
            "webauthn.home.koehntopp.de",
            "--source",
            "git@github.com:isotopp/webauthn-test.git",
            "--username",
            "webauthn",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"project_type": "wsgi_site"' in out
    assert '"source": "git@github.com:isotopp/webauthn-test.git"' in out


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
    assert "systemctl stop httpd.service" in (configtest_prefix / "cmdlog.sh").read_text(
        encoding="utf-8"
    )

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


def test_update_in_configtest_logs_git_commands_for_wsgi(tmp_path, capsys) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "webauthn").write_text(
        (
            '{"type":"wsgi_site","project":"webauthn","hostname":"webauthn.home.koehntopp.de",'
            '"source":"git@github.com:isotopp/webauthn-test.git","username":"webauthn",'
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
    assert "cd /home/webauthn/webauthn" in cmdlog
    assert "git reset --hard" in cmdlog
    assert "git pull --rebase" in cmdlog
    assert "venv/bin/python -m pip install -r requirements.txt" in cmdlog


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
