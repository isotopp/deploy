from deploy.gitops import discover_updater


def test_discover_updater_from_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        (
            '[project]\nname = "demo"\nversion = "0.1.0"\n'
            '[tool.deploy]\nupdater = ["uv", "run", "python", "-m", "demo.update"]\n'
        ),
        encoding="utf-8",
    )

    updater = discover_updater(tmp_path)

    assert updater == ("uv", "run", "python", "-m", "demo.update")
