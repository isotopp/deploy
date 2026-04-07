from deploy.models import (
    GoSiteProject,
    ProxyProject,
    RedirectSiteProject,
    WsgiSiteProject,
    project_from_record,
)


def test_loads_legacy_proxy_record() -> None:
    project = project_from_record(
        {
            "type": "proxy",
            "project": "immich",
            "hostname": "immich.home.koehntopp.de",
            "port": 2283,
        }
    )

    assert isinstance(project, ProxyProject)
    assert project.upstream_host == "127.0.0.1"
    assert project.upstream_port == 2283
    assert project.upstream_scheme == "http"


def test_loads_legacy_wsgi_record() -> None:
    project = project_from_record(
        {
            "type": "wsgi_site",
            "project": "webauthn",
            "hostname": "webauthn.home.koehntopp.de",
            "github": "git@github.com:isotopp/webauthn-test.git",
            "username": "webauthn",
            "projectdir": "webauthn",
            "home": "/home/webauthn",
        }
    )

    assert isinstance(project, WsgiSiteProject)
    assert project.source_type == "git"
    assert project.source == "git@github.com:isotopp/webauthn-test.git"
    assert project.project_dir == "webauthn"


def test_loads_redirect_typo_compatibility() -> None:
    project = project_from_record(
        {
            "type": "redirect_site",
            "project": "oldsite",
            "hostname": "old.example.com",
            "to_hostame": "new.example.com",
        }
    )

    assert isinstance(project, RedirectSiteProject)
    assert project.to_hostname == "new.example.com"


def test_loads_legacy_go_site_record() -> None:
    project = project_from_record(
        {
            "type": "go_site",
            "project": "wiki",
            "hostname": "wiki.snackbag.net",
            "github": "git@github.com:snackbag/wiki.git",
            "username": "wiki",
            "projectdir": "wiki",
            "home": "/home/wiki",
            "port": 3001,
        }
    )

    assert isinstance(project, GoSiteProject)
    assert project.source_type == "git"
    assert project.upstream_port == 3001
    assert project.project_dir == "wiki"
