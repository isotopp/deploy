from deploy.apache import render_site_config
from deploy.models import ProxyProject, WsgiSiteProject


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
        source="git@github.com:isotopp/webauthn-test.git",
        username="webauthn",
        project_dir="webauthn",
        home="/home/webauthn",
    )

    config = render_site_config(project)

    assert "Use PyApp webauthn.home.koehntopp.de webauthn" in config.content
    assert "/home/webauthn/webauthn" in config.content
