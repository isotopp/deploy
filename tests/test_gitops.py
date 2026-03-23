from deploy.gitops import (
    build_update_plan,
    clone_command,
    discover_updater,
    local_git_safe_directories,
)
from deploy.models import StaticSiteProject


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


def test_clone_command_for_local_git_uses_safe_directory(tmp_path) -> None:
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    source.mkdir()
    project = StaticSiteProject(
        name="demo",
        project_type="static_site",
        hostname="demo.example.com",
        source_type="local_git",
        source=str(source),
        username="demo",
        project_dir="checkout",
        home="/home/demo",
    )

    command = clone_command(project, checkout)

    assert command == (
        "git",
        "clone",
        str(source.resolve()),
        str(checkout),
    )


def test_local_git_safe_directories_contains_source_and_git_dir(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    project = StaticSiteProject(
        name="demo",
        project_type="static_site",
        hostname="demo.example.com",
        source_type="local_git",
        source=str(source),
        username="demo",
        project_dir="checkout",
        home="/home/demo",
    )

    safe_directories = local_git_safe_directories(project)

    assert safe_directories == (str(source.resolve()), str(source.resolve() / ".git"))


def test_update_plan_for_local_git_uses_plain_git_pull(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    working_tree = tmp_path / "home" / "demo" / "checkout"
    working_tree.mkdir(parents=True)
    project = StaticSiteProject(
        name="demo",
        project_type="static_site",
        hostname="demo.example.com",
        source_type="local_git",
        source=str(source),
        username="demo",
        project_dir="checkout",
        home=str(working_tree.parent),
    )

    plan = build_update_plan(project)

    assert plan.supported is True
    assert plan.commands[0] == ("git", "reset", "--hard")
    assert plan.commands[1] == ("git", "pull", "--rebase")
