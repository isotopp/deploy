import json

from deploy.project_store import ProjectStore


def test_lists_and_loads_projects(tmp_path) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "grafana").write_text(
        json.dumps(
            {
                "type": "proxy",
                "project": "grafana",
                "hostname": "grafana.home.koehntopp.de",
                "port": 3000,
            }
        ),
        encoding="utf-8",
    )

    store = ProjectStore(project_dir)

    assert store.list_names() == ["grafana"]
    project = store.load("grafana")
    assert project.name == "grafana"
    assert project.hostname == "grafana.home.koehntopp.de"
