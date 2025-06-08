# Usage

The Python script deploy supports six deployment types, each corresponding to a value in the VALID_PROJECT_TYPES list:

Deployment Types:
- `static_site`
- `redirect_site`
- `wsgi_site`
- `discord_bot`
- `go_site`
- `proxy`

## How to call `deploy` for each deployment type:

Each deployment requires the create operation with additional arguments, depending on its type.
Below is a table summarizing the required and optional arguments for each type.

|  Type | Required Arguments                                                                             | Notes                                                                                                        |
|-----------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `static_site`   | `--type static_site` <br/> `--github <git@github.com:...>` <br/> `--hostname <...>`            | Clones repo, sets up Apache static host<br/>Hostnames must be in SSLDOMAINS (`snackbag.net`, `minenet.group`) |
| `redirect_site` | `--type redirect_site` <br/> `--hostname <...>` <br/> `--to-hostname <...>`                    | No git repo required                                                                                         |
| `wsgi_site`     | `--type wsgi_site` <br/> `--hostname <...>` <br/> `--github <git@github.com:...>`              | Python virtualenv + Apache WSGI                                                                              |
| `discord_bot`   | `--type discord_bot` <br/> `--hostname <...>` <br/> `--github <git@github.com:...>`            | Sets up a systemd service written in Python                                                                  |
| `go_site`       | `--type go_site` <br/> `--hostname <...>` <br/> `--github <git@github.com:...>` `--port <int>` | Builds Go binary, systemd service + Apache reverse proxy                                                     |
| `proxy`         | `--type proxy` <br/> `--hostname <...>` <br/> `--port <int>`                                   | Reverse proxy only, no repo required                                                                         |

## Examples

### Create a static site

```bash
deploy create mysite --type static_site --github git@github.com:user/repo.git --hostname mysite.snackbag.net
```

### Redirect Site

```bash
deploy create redirectme --type redirect_site --hostname old.snackbag.net --to-hostname new.snackbag.net
```

### WSGI Site

```bash
deploy create pyapp --type wsgi_site --github git@github.com:user/app.git --hostname pyapp.snackbag.net
```

### Discord Bot

```bash
deploy create mybot --type discord_bot --github git@github.com:user/bot.git --hostname bot.snackbag.net
```

### Go Site

```bash
deploy create wiki --type go_site --github git@github.com:snackbag/wiki.git --hostname wiki.snackbag.net --port 3001
```

### Proxy

```bash
deploy create internal --type proxy --hostname internal.snackbag.net --port 9000
```

# Other Commands

Besides create, the deploy script supports seven other operations.
Each is listed in VALID_OPERATIONS and handled in the main() function.

| Operation | Purpose                                                 | Example                                         |
|-----------|---------------------------------------------------------|-------------------------------------------------|
| `create`  | Create a new deployment                                 | `deploy create <project> --type ... [options]`  |
| `delete` | Remove a deployment and all config                      | `deploy delete <project>`                       |
| `show` | Show all deployments or the specifics on one deployment | `deploy show projects`, `deploy show <project>` |
| `logs` | Tail the logs for the deployment                        | `deploy logs <project>`                         |
| `start`| Start services for a project                            | `deploy start <project>`                        |
| `stop`| Stop services for a project                             | `deploy stop <project>`                         |
| `restart` | Restart systemd/apache for a project                    | `deploy restart <project>`                      |
| `update` | Git pull and update dependencies                        | `deploy update <project>`                       |

