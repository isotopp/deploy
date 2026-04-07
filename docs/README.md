# Deploy Administration Guide

This directory contains sysadmin-oriented documentation for `deploy`.

Recommended reading order:

1. [Installation And Bootstrap](/Users/kris/Source/codex/docs/01-installation-and-bootstrap.md)
2. [Testing And Safe Generation](/Users/kris/Source/codex/docs/02-testing-and-safe-generation.md)
3. [Site Lifecycle](/Users/kris/Source/codex/docs/03-site-lifecycle.md)
4. [Site Types](/Users/kris/Source/codex/docs/04-site-types.md)
5. [Adopting Legacy Sites](/Users/kris/Source/codex/docs/05-adopting-legacy-sites.md)

The current deploy model supports these site types:

- `static`
- `wsgi`
- `redirect`
- `proxy`
- `custom`
- `go`

The main commands are:

- `deploy show`
- `deploy create`
- `deploy adopt`
- `deploy restart`
- `deploy start`
- `deploy stop`
- `deploy update`
- `deploy logs`
- `deploy delete`
- `deploy bootstrap-apache`

Typical workflow:

1. Install the tool with `uv tool install .`
2. Bootstrap Apache shared config
3. Use `--dry-run` and `--configtest` before touching live config
4. Create or adopt site records
5. Operate sites with `show`, `restart`, `update`, `logs`, and `delete`

