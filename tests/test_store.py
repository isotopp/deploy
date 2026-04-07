import json

from deploy.project_store import ProjectStore
from deploy.runtime import ExecutionContext, RunMode


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


def test_list_names_ignores_fragment_files(tmp_path) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "kris").write_text(
        '{"type":"custom","project":"kris","hostname":"kris.home.koehntopp.de","config":true}\n',
        encoding="utf-8",
    )
    (project_dir / "kris.conf").write_text(
        "<VirtualHost *:443>\n</VirtualHost>\n",
        encoding="utf-8",
    )

    store = ProjectStore(project_dir)

    assert store.list_names() == ["kris"]


def test_configtest_store_lists_and_loads_staged_projects(tmp_path) -> None:
    project_dir = tmp_path / "projects"
    store = ProjectStore(
        project_dir,
        context=ExecutionContext(mode=RunMode.CONFIGTEST, configtest_prefix=tmp_path / "stage"),
    )
    staged_dir = (tmp_path / "stage") / project_dir.relative_to(project_dir.anchor)
    staged_dir.mkdir(parents=True)
    (staged_dir / "grafana").write_text(
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

    assert store.list_names() == ["grafana"]
    project = store.load("grafana")
    assert project.hostname == "grafana.home.koehntopp.de"


def test_load_supported_projects_skips_unsupported_records(tmp_path) -> None:
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    (project_dir / "grafana").write_text(
        '{"type":"proxy","project":"grafana","hostname":"grafana.home.koehntopp.de","port":3000}\n',
        encoding="utf-8",
    )
    (project_dir / "legacy-bot").write_text(
        '{"type":"discord_bot","project":"legacy-bot","hostname":"bot.example.invalid"}\n',
        encoding="utf-8",
    )

    store = ProjectStore(project_dir)

    projects, warnings = store.load_supported_projects()

    assert [project.name for project in projects] == ["grafana"]
    assert warnings == [
        "skipping unsupported project record legacy-bot: unsupported project type: discord_bot"
    ]
