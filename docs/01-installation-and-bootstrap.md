# Installation And Bootstrap

## Install The Tool

The intended installation mode is a normal `uv` tool install from a checked out repository.

Example:

```sh
git clone <repo-url> ~/Source/deploy
cd ~/Source/deploy
uv tool install .
```

This installs the `deploy` entrypoint into your `uv` tool bin directory.

Example:

```sh
deploy --help
deploy create --help
deploy bootstrap-apache --help
```

If you prefer to run from a working tree during development:

```sh
cd ~/Source/deploy
uv run deploy --help
```

## What Bootstrap-Apache Manages

`bootstrap-apache` manages the shared Apache layer, not per-site project files.

That includes:

- `/etc/httpd/conf/httpd.conf`
- `/etc/httpd/conf.d/macros.conf`
- `/etc/httpd/conf.d/ssldomain.conf`
- `/etc/httpd/conf.d/ssl.conf`
- selected module config files such as:
  - `00-brotli.conf`
  - `00-dav.conf`
  - `01-cgi.conf`
- Apache include setup for `conf.sites.d/*.conf`

It does not create project records or deploy application source trees.

## Bootstrap Modes

### Default

`deploy bootstrap-apache`

This writes the deploy-managed Apache shared files and ensures the site include is present.

Example:

```sh
deploy bootstrap-apache
```

### IP Refresh Only

`deploy bootstrap-apache --ip`

This only refreshes the `/server-status` and `/server-info` ACL lines in `httpd.conf`.

By default it discovers the external IP by HTTP request.

Example:

```sh
deploy bootstrap-apache --ip
```

You can add extra permitted IPs:

```sh
deploy bootstrap-apache --ip --additional-ip 62.166.154.246 --additional-ip 5.9.55.232
```

### Full Baseline Replacement

`deploy bootstrap-apache --all`

This is the heavy bootstrap path.

Behavior:

- removes `/etc/httpd.bak` if it already exists
- moves `/etc/httpd` to `/etc/httpd.bak`
- recreates `/etc/httpd`
- writes the managed baseline directly

Example:

```sh
deploy bootstrap-apache --all
```

Use `--all` only when you actually want to replace the host baseline. For an already-running host, prefer config testing first.

## Typical Bootstrap Sequence

For a new host:

```sh
deploy --configtest /root/httpd-bootstrap bootstrap-apache --all
diff -ur /etc/httpd /root/httpd-bootstrap/etc/httpd
deploy bootstrap-apache --all
apachectl configtest
systemctl restart httpd
```

For an existing host where only the status ACL changed:

```sh
deploy --configtest /root/httpd-ip bootstrap-apache --ip --additional-ip 5.9.55.232
diff -u /etc/httpd/conf/httpd.conf /root/httpd-ip/etc/httpd/conf/httpd.conf
deploy bootstrap-apache --ip --additional-ip 5.9.55.232
```
