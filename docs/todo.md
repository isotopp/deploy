
# Argument Parsing Refactor (Subcommands)

    Replace --type flag with subcommands
    Use argparse.ArgumentParser(...).add_subparsers() to define:

        deploy create static_site

        deploy create redirect_site

        deploy create proxy

        etc.

    Define a subparser for each project type under create
    Each subparser should only accept relevant arguments:

        static_site: --hostname, --github, --username, --projectdir

        redirect_site: --hostname, --to-hostname

        proxy: --hostname, --port

    Move validation logic for each type to subparser-level
    Let argparse handle required/optional args.

    Make project a required positional argument for all commands where relevant

# Object-Oriented Refactor

    Create a base class Project
    Define shared attributes and methods:

```python
class Project:
    def __init__(self, config: dict): ...
    def create(self): ...
    def delete(self): ...
    def start(self): ...
    def stop(self): ...
    def update(self): ...
    def restart(self): ...
    def logs(self): ...
```

Create a subclass for each project type

```python
class StaticSite(Project):
    def create(self): ...
    def delete(self): ...
```

Replace large if/elif blocks in do_create, do_delete, etc. with dynamic dispatch

```python
PROJECT_TYPE_MAP = {
    "static_site": StaticSite,
    ...
}
project_cls = PROJECT_TYPE_MAP[args.type]
project = project_cls(config)
project.create()
```

## Encapsulate System Services as Classes

    Create SystemdService class
    Methods: create(), delete(), enable(), disable(), restart(), status()

    Create ApacheConfig class
    Methods: create(), delete()

    Create SyslogConfig class
    Methods: create(), delete()

    Create UserAccount class
    Methods: create(), delete(), home_path()

    Create DeploymentDirectory class
    Methods: clone_repo(), build_go(), setup_python(), create_symlink(), etc.
       Actually, make this a Python deployment, a Go deployment, a Java deployment

# General Cleanup

    Move project config handling (load_project_config) into Project class

    Remove all args.<key> lookups outside of argument parsing

    Replace global args with scoped config objects passed to class constructors

    Rename utility functions (run, to_file, etc.) and consider making them static methods or moving to a utils module

