# Testing And Safe Generation

`deploy` has two built-in safe modes:

- `--dry-run`
- `--configtest <prefix>`

These are the normal ways to validate changes before touching live Apache or system state.

## Dry Run

`--dry-run` does not write files and does not run commands.

Use it for:

- quick CLI validation
- checking parsed project data
- checking whether a command is supported

Example:

```sh
deploy --dry-run create proxy grafana --hostname grafana.example.net --upstream-port 3000
```

Example with JSON:

```sh
deploy --json --dry-run create wsgi webauthn \
  --hostname webauthn.example.net \
  --source-type git \
  --source git@github.com:example/webauthn.git \
  --username webauthn
```

## Config Test

`--configtest <prefix>` writes staged output under a prefix and logs commands to `cmdlog.sh` instead of running them.

Use it for:

- diffing generated Apache config
- previewing systemd units
- previewing site deletion effects
- previewing TLS regeneration

Example:

```sh
deploy --configtest /root/testconfig restart wiki
```

This will stage files such as:

- `/root/testconfig/etc/httpd/conf.sites.d/wiki.example.net.conf`
- `/root/testconfig/etc/httpd/conf.d/ssldomain.conf`
- `/root/testconfig/cmdlog.sh`

Example inspection:

```sh
find /root/testconfig -type f | sort
sed -n '1,80p' /root/testconfig/etc/httpd/conf.sites.d/wiki.example.net.conf
sed -n '1,40p' /root/testconfig/etc/httpd/conf.d/ssldomain.conf
sed -n '1,200p' /root/testconfig/cmdlog.sh
```

## JSON Output

Most read-oriented commands support `--json`.

Use it when:

- you want structured output for scripts
- you want to inspect warnings precisely
- you want to validate staged file locations

Example:

```sh
deploy --json --configtest /root/testconfig restart wiki
```

## Comparing Generated Config To Live Config

Typical workflow:

```sh
deploy --project-dir ~/projects --configtest ~/testconfig restart extras
diff -u /etc/httpd/conf.sites.d/extras.example.net.conf \
  ~/testconfig/etc/httpd/conf.sites.d/extras.example.net.conf
```

For the TLS domain set:

```sh
grep '^MDomain ' /etc/httpd/conf.d/ssldomain.conf | tr ' ' '\n' | sort > /tmp/live-domains
grep '^MDomain ' ~/testconfig/etc/httpd/conf.d/ssldomain.conf | tr ' ' '\n' | sort > /tmp/test-domains
diff -u /tmp/live-domains /tmp/test-domains
```

## Local Test Suite

The repository uses:

- `pytest`
- `ty`
- `ruff`

Run all checks:

```sh
uv run pytest
uv run ty check
uv run ruff check --fix src tests
```

Example before a host rollout:

```sh
uv run pytest
deploy --configtest /root/testconfig restart snackbag
apachectl configtest
```

