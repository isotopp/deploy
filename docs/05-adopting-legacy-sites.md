# Adopting Legacy Sites

`adopt` exists for the situation where the server already has:

- a real Unix user
- a real home directory
- a real checkout with state
- possibly manual service state

and you want `deploy` to begin managing Apache and metadata without recreating the world.

## Why Adopt Exists

Fresh `create` is intentionally destructive-safe:

- it expects a new user
- it expects a new home
- it expects a new checkout

That is correct for new sites, but wrong for long-lived hosts with existing application state.

`adopt` attaches deploy metadata to that existing state instead.

## Supported Adopt Types

Currently:

- `adopt static`
- `adopt wsgi`
- `adopt go`

There is no reason to adopt `redirect`, `proxy`, or `custom`, because they do not own source-backed runtime state in the same way.

## What Adopt Does

`adopt`:

- verifies the user exists
- verifies the home directory exists
- verifies the checkout path exists
- writes the project record
- writes the Apache site file
- regenerates `ssldomain.conf`
- restarts Apache

`adopt` does not:

- create the user
- clone a repo
- run `uv sync`
- run `go build`
- delete anything

## Example: Adopt A WSGI Site

```sh
deploy adopt wsgi extras \
  --hostname extras.snackbag.net \
  --source-type git \
  --source git@github.com:vijfhuizen-c0derz/SnackBag-Extras.git \
  --username extras \
  --project-dir-name extras \
  --home /home/extras
```

Example safe preview:

```sh
deploy --configtest /root/testconfig adopt wsgi extras \
  --hostname extras.snackbag.net \
  --source-type git \
  --source git@github.com:vijfhuizen-c0derz/SnackBag-Extras.git \
  --username extras \
  --project-dir-name extras \
  --home /home/extras
```

## Example: Adopt A Go Site

```sh
deploy adopt go wiki \
  --hostname wiki.snackbag.net \
  --source-type git \
  --source git@github.com:snackbag/wiki.git \
  --username wiki \
  --project-dir-name wiki \
  --home /home/wiki \
  --upstream-port 3001
```

For `go`, the upstream port is required in the new record format because Apache needs it for `ProxyVHost`.

## Managed Flags

Adopted source-backed records are written with:

- `managed_user: false`
- `managed_checkout: false`

That means:

- `delete` will not remove the user automatically
- `update` becomes stricter and checks the checkout before making changes

This is deliberate. Adopt is for existing state you do not want deploy to destroy casually.

## Delete Behavior For Adopted Sites

If you delete an adopted source-backed site, `deploy` removes:

- the project record
- the Apache site file
- TLS references

It does not remove the user automatically. Instead it warns and tells you to inspect and run the archival and `userdel` commands manually if you really want that.

Example warning shape:

- deploy refuses to delete unmanaged user `kris-web`
- it shows you the `tar --exclude ...` and `userdel -r ...` commands to run manually after inspection

## Update Behavior For Adopted Sites

For adopted source-backed sites, `update` checks:

- the working tree exists
- it is actually a git checkout
- the configured `origin` matches the project source

If those checks fail, `update` stops and tells you to inspect the repo manually.

This avoids accidental destructive updates against the wrong working tree.

## Legacy Record Migration

When migrating legacy project records:

- use `project_dir` in new records
- do not rely on old `projectdir` except for legacy compatibility
- set `managed_user: false`
- set `managed_checkout: false`

Example migrated adopted record:

```json
{
  "type": "wsgi_site",
  "project": "extras",
  "hostname": "extras.snackbag.net",
  "source_type": "git",
  "source": "git@github.com:vijfhuizen-c0derz/SnackBag-Extras.git",
  "username": "extras",
  "project_dir": "extras",
  "home": "/home/extras",
  "managed_user": false,
  "managed_checkout": false
}
```

