from types import SimpleNamespace

from deploy.command_common import CommonOptions
from deploy.models import StaticSiteProject
from deploy.runtime import ExecutionContext, RunMode
from deploy.source_backed import (
    managed_user_gecos,
    managed_user_matches_hostname,
    purge_source_backed_project,
)


def test_managed_user_gecos_matches_exact_hostname() -> None:
    hostname = "keks.home.koehntopp.de"

    assert managed_user_gecos(hostname) == "Website owner keks.home.koehntopp.de"
    assert managed_user_matches_hostname(
        gecos="Website owner keks.home.koehntopp.de",
        hostname=hostname,
    )
    assert not managed_user_matches_hostname(
        gecos="Kris Koehntopp",
        hostname=hostname,
    )
    assert not managed_user_matches_hostname(
        gecos="Website owner other.home.koehntopp.de",
        hostname=hostname,
    )


def test_live_purge_refuses_unmanaged_user(monkeypatch, tmp_path) -> None:
    project = StaticSiteProject(
        name="kris",
        project_type="static_site",
        hostname="kris.home.koehntopp.de",
        source_type="local_git",
        source="/home/kris/Source/kris",
        username="kris",
        project_dir="checkout",
        home="/home/kris-web",
    )
    options = CommonOptions(
        json_output=False,
        execution=ExecutionContext(mode=RunMode.LIVE),
        project_dir=tmp_path / "projects",
        apache_sites_dir=tmp_path / "sites",
        apache_tls_config=tmp_path / "conf.d" / "ssldomain.conf",
        machine_fqdn="server.home.koehntopp.de",
    )
    called_commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        "deploy.source_backed.pwd.getpwnam",
        lambda username: SimpleNamespace(pw_gecos="Kris Koehntopp"),
    )
    monkeypatch.setattr(
        "deploy.source_backed.CommandRunner.run",
        lambda self, argv, **kwargs: called_commands.append(tuple(argv)),
    )
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

    backup_path, warnings = purge_source_backed_project(project, options)

    assert backup_path is None
    assert called_commands == []
    assert "refusing to delete unmanaged user kris" in warnings[0]
