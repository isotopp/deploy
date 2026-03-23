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
    assert '"phase": "preview"' in out
    assert '"project_type": "proxy"' in out


def test_create_wsgi_subcommand_parses_type_specific_options(capsys) -> None:
    exit_code = main(
        [
            "--json",
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
