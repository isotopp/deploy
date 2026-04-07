from deploy.apache import render_site_config
from deploy.models import GoSiteProject, ProxyProject, StaticSiteProject, WsgiSiteProject


def test_renders_simple_proxy_macro_output() -> None:
    project = ProxyProject(
        name="immich",
        project_type="proxy",
        hostname="immich.home.koehntopp.de",
        upstream_host="127.0.0.1",
        upstream_port=2283,
    )

    config = render_site_config(project)

    assert config.filename == "immich.home.koehntopp.de.conf"
    assert "Use ProxyVHost immich.home.koehntopp.de 2283" in config.content


def test_renders_wsgi_macro_output() -> None:
    project = WsgiSiteProject(
        name="webauthn",
        project_type="wsgi_site",
        hostname="webauthn.home.koehntopp.de",
        source_type="git",
        source="git@github.com:isotopp/webauthn-test.git",
        username="webauthn",
        project_dir="webauthn",
        home="/home/webauthn",
    )

    config = render_site_config(project)

    assert "Use PyApp webauthn.home.koehntopp.de webauthn" in config.content
    assert "/home/webauthn/webauthn" in config.content


def test_renders_static_macro_output_with_docroot() -> None:
    project = StaticSiteProject(
        name="keks",
        project_type="static_site",
        hostname="keks.home.koehntopp.de",
        source_type="local_git",
        source="/home/codex/site",
        username="keks",
        project_dir="checkout",
        home="/home/keks",
    )

    config = render_site_config(project)

    assert "Use StaticVHost keks.home.koehntopp.de /home/keks/checkout" in config.content


def test_renders_go_site_as_proxy_macro_output() -> None:
    project = GoSiteProject(
        name="wiki",
        project_type="go_site",
        hostname="wiki.snackbag.net",
        source_type="git",
        source="git@github.com:snackbag/wiki.git",
        username="wiki",
        project_dir="checkout",
        upstream_port=3001,
        home="/home/wiki",
    )

    config = render_site_config(project)

    assert "Use ProxyVHost wiki.snackbag.net 3001" in config.content
