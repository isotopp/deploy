# Site Types

This page describes the supported project types and their expected fields.

## Static

`static` is for a source-backed static web tree served directly by Apache.

Example create:

```sh
deploy create static snackbag \
  --hostname www.snackbag.net \
  --source-type git \
  --source git@github.com:snackbag-net/empty-site.git \
  --username snackbag
```

Generated Apache shape:

```apache
Use StaticVHost www.snackbag.net /home/snackbag/checkout
```

## Wsgi

`wsgi` is for a Python WSGI application with a deployed checkout and `uv sync`.

Example create:

```sh
deploy create wsgi webauthn \
  --hostname webauthn.example.net \
  --source-type git \
  --source git@github.com:example/webauthn.git \
  --username webauthn
```

Generated Apache shape:

```apache
Use PyApp webauthn.example.net webauthn /home/webauthn/checkout webauthn webauthn
```

Expected project layout:

- `pyproject.toml`
- `uv lock`
- WSGI entrypoint such as `app.wsgi`
- deployed tree readable by Apache

## Redirect

`redirect` is a pure Apache redirect site. It has no source tree and no user lifecycle.

Example:

```sh
deploy create redirect snackbagnowww \
  --hostname snackbag.net \
  --to-hostname www.snackbag.net
```

Generated Apache shape:

```apache
Use RedirectVHost snackbag.net www.snackbag.net
```

## Proxy

`proxy` is the simple legacy reverse-proxy type.

Example:

```sh
deploy create proxy grafana \
  --hostname grafana.snackbag.net \
  --upstream-port 3000
```

Generated Apache shape:

```apache
Use ProxyVHost grafana.snackbag.net 3000
```

This is the narrow simple model. Complex proxy sites are usually better handled as `custom` until they have a richer typed representation.

## Custom

`custom` stores a normal project record plus a sibling Apache fragment file.

Use it for:

- hand-written Apache vhosts
- odd proxy rules
- sites that do not fit the current typed schema

Example:

```sh
deploy create custom artifacts \
  --hostname artifacts.snackbag.net \
  --config-file ./artifacts.conf
```

This stores:

- `/etc/projects/artifacts`
- `/etc/projects/artifacts.conf`

## Go

`go` is a source-backed Go application managed as a systemd service and exposed through Apache proxying.

Example:

```sh
deploy create go wiki \
  --hostname wiki.snackbag.net \
  --source-type git \
  --source git@github.com:snackbag/wiki.git \
  --username wiki \
  --upstream-port 3001
```

Generated Apache shape:

```apache
Use ProxyVHost wiki.snackbag.net 3001
```

Create also handles:

- Go build
- systemd unit generation
- service enable/start

## When To Use Custom Instead Of A Typed Site

Use `custom` when:

- the vhost already exists as a hand-written Apache file
- the site needs complicated path-based proxy rules
- the site needs unusual headers or rewrites
- you want deploy to manage the file without first designing a schema

Examples:

- a complex `openwebui` proxy
- a mixed static and alias-heavy site
- a manual Artifactory vhost

