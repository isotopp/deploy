# Notes

## Deploy Tool

- Development constraints:
  - target runtime is `uv` with `--managed-python`, not the system Python
  - preferred CLI shape is `uv run --managed-python deploy create <type> <name> ...`,
    or later, after `uv tool install https://github.com/...`, a simple `deploy create ...`.
  - create-time options should be type-specific, not one shared option bag
  - source trees may come from local Git trees or generic repo URLs, not only `git@github.com`
  - read-oriented commands should support `--json` output
  - Python style preferences: `dataclasses`, `pathlib`, and `httpx` if HTTP is needed
  - project tooling preferences: `pytest`, `ty`, and `ruff`
  - bump `project.version` in `pyproject.toml` with `uv version ...`, not by manual file edits
  - after the final local validation pass and commit, push to `origin` unless the user says not to

## /etc/projects

- `/etc/projects` is a directory of per-project JSON files
- Confirmed entries:
  - `grafana`: proxy to port 3000
  - `immich`: proxy to port 2283
  - `navidrome`: proxy to port 4533
  - `plik`: proxy to port 8084
  - `webauthn`: WSGI app from `/home/webauthn/webauthn`

## Apache Config Generation

- `deploy` reads project JSON from `/etc/projects/<project>`
- `deploy` writes Apache snippets to `/etc/httpd/conf.sites.d/<hostname>.conf`
- Confirmed generated forms:
  - `Use ProxyVHost <hostname> <port>`
  - `Use PyApp <hostname> <project> <appdir> <unixuser> <unixgroup>`
  - `Use VHost <hostname>`
  - `Use RedirectVHost <hostname> <to_hostname>`
