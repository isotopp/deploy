# Site Lifecycle

This page covers the normal operational commands after a project record exists.

## Show

`show` displays a single project or the list of projects.

Examples:

```sh
deploy show projects
deploy show snackbag
deploy --json show wiki
```

For a `custom` project, `show` also includes the stored config fragment.

## Export

`export <name>` writes the project JSON to `./<name>`.

If the project has a fragment, it also writes `./<name>.conf`.

Example:

```sh
cd /root
deploy export wiki
```

This produces:

- `/root/wiki`
- `/root/wiki.conf` if the project has a fragment

## Import

`import <name>` reads `./<name>` and optional `./<name>.conf`, validates the project definition, writes it to `/etc/projects`, regenerates Apache/TLS state, and restarts Apache.

Import rejects project type changes for an existing project record.

Examples:

```sh
cd /root
deploy import wiki
deploy --configtest /root/testconfig import wiki
```

## Restart

`restart <name>` rewrites the project Apache site config, regenerates TLS state, and restarts Apache.

For `go` sites it also restarts the systemd service.

Examples:

```sh
deploy restart snackbag
deploy restart wiki
```

Example safe preview:

```sh
deploy --configtest /root/testconfig restart wiki
```

## Start

`start <name>` writes site state and starts Apache.

For `go` sites it also starts the service.

Examples:

```sh
deploy start snackbag
deploy start wiki
```

## Stop

`stop <name>` stops Apache.

For `go` sites it also stops the service.

Examples:

```sh
deploy stop snackbag
deploy stop wiki
```

## Update

`update <name>` updates a source-backed deployed working tree.

Behavior depends on site type:

- `static`
  - `git reset --hard`
  - `git pull --rebase`
- `wsgi`
  - `git reset --hard`
  - `git pull --rebase`
  - `uv sync`
  - optional updater from `pyproject.toml`
- `go`
  - `git reset --hard`
  - `git pull --rebase`
  - `go build`
  - `systemctl restart <service>`
- `proxy`, `redirect`, `custom`
  - no source-backed update workflow

Examples:

```sh
deploy update snackbag
deploy update webauthn
deploy update wiki
```

For adopted sites, `update` is conservative:

- it checks that the working tree is a git checkout
- it checks that the checkout `origin` matches the configured source
- if not, it stops and tells you to inspect the repo manually

## Logs

`logs <name>` tails runtime logs.

For most sites:

- `/var/log/httpd/error-<hostname>.log`
- `/var/log/httpd/access-<hostname>.log`

For `go` sites:

- Apache logs
- `journalctl -u <service>.service -f`

Examples:

```sh
deploy logs snackbag
deploy logs webauthn
deploy logs wiki
```

## Delete

`delete <name>` removes deploy metadata and Apache site config, regenerates TLS state, and restarts Apache.

For deploy-managed source-backed sites it may also:

- archive the home directory to `/home/<user>.tgz`
- remove the Unix user

This only happens when the project is marked as managing that user and the GECOS safety check matches.

Examples:

```sh
deploy delete snackbag
deploy delete wiki
```

Force mode is for recovery cleanup:

```sh
deploy delete --force broken-site
```

`--force` continues cleanup best-effort and reports warnings instead of aborting on every failure.
