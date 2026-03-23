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
            "static-site",
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
    assert "git config --global --add safe.directory " in cmdlog
    assert "/home/codex/site" in cmdlog
    assert "/home/codex/site/.git" in cmdlog
    assert "git clone /home/codex/site /home/keks/checkout" in cmdlog
    assert "uv sync" not in cmdlog


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


def test_delete_source_backed_in_configtest_logs_backup_and_userdel(tmp_path, capsys) -> None:
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
    assert "sudo -u webauthn -- sh -lc 'cd /home/webauthn/webauthn && exec uv sync'" in cmdlog


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
    assert "cd /home/keks/checkout && exec git reset --hard" not in cmdlog
    assert "cd /home/keks/checkout && exec git pull --rebase" not in cmdlog
    assert "cd /home/keks/checkout" in cmdlog
    assert "\ngit pull --rebase\n" in cmdlog


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
            "wsgi-site",
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
    assert "git config --global --add safe.directory " in cmdlog
    assert str(source_dir.resolve()) in cmdlog
    assert str(source_dir.resolve() / ".git") in cmdlog
    assert f"git clone {source_dir.resolve()} /home/demo/checkout" in cmdlog
    assert "sudo -u demo -- sh -lc 'cd /home/demo/checkout && exec uv sync'" in cmdlog
    assert "sudo -u demo -- sh -lc 'cd /home/demo/checkout && exec ln -sfn .venv venv'" in cmdlog
    assert (
        "sudo -u demo -- sh -lc 'cd /home/demo/checkout && exec uv run python -m demo.update'"
    ) in cmdlog


def test_create_rejects_existing_user(tmp_path) -> None:
    try:
        main(
            [
                "create",
                "wsgi-site",
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
