# Projects: JSON Format and Actions

The various services on the machine are configured with JSON files in `/etc/projects`.
At this point we support three types of Projects:

- static_site
- wsgi_site
- discord_bot

Each JSON file has a field `type` that is set to exactly one of these three type values.
The type of project determines what other attributes must be present to make this a valid project,
and which actions are taken on project creation, deletion or as a deploy action.

# static_site Projects

## JSON ##

Attributes:

`type: static_site`
: The type `static_site` sets this project type as a static site.

`hostname: <hostname>.snackbag.net`
: The value of the `hostname` attribute determines the domain name, under which the site will be online.
The domain name has to end with `.snackbag.net`.

`github: "git@github.com:...`
: The URL that holds the content for the site.
It has to start with `git@github.com:`

`username` 
: All content is owned by this user.

## Creation Flow

Invariants:

- hostname must not exist.
- Implied values must not be specified
  (projectdir, username, update_cmd, log_cmd and restart_cmd).

1. Create a user, `.ssh` dir, and ssh-key and ssh-identity config for the site.
2. Check out `github` into `/home/user/projectdir` using `deploykey`.
3. Create `/etc/projects` entry.
4. Create apache config.
5. Restart apache, collecting Domains.

# Create a WSGI site

## JSON

Attributes:

`type: wsgi_site`
: The type `wsgi_site` sets this project type as a Python project using a WSGI container.

`hostname: <hostname>.snackbag.net`
: The value of the `hostname` attribute determines the domain name, under which the site will be online.
The domain name has to end with `.snackbag.net`.

`github: "git@github.com:...`
: The URL that holds the content for the site.
It has to start with `git@github.com:`

`deploykey: /pathname`
: The path to a `ssh` deploy keypair.
The name refers to the private key.
The public key must be in the same directory, with the same name + `.pub`.
Both files have to readable for the `deploy` program.

`username`:
: The `username` under which the project runs.

`projectdir`:
: Subdirectory in the users home, so `/home/<username>/<projectdir>`.

`update_cmd`:
: Usually `/usr/local/bin/pip_and_pull`.

`log_cmd`:
: Usually `/usr/local/bin/show_wsgi_log <project>`.

`restart_cmd`:
: Usually `/usr/local/bin/restart_apache`.

## Creation Flow

Invariants:

- hostname must not exist.
- username must not exist.

Also, the deploykey must be set for the github repository in order for the initial checkout to work.

1. Create a user
2. Create ssh config (key, config)
3. Create `/etc/projects` entry.
4. Check out `github` into `/home/user/projectdir` using `deploykey`.
5. Python venv, pip und pull.
6. Apache Config "Use PyApp Macro"
7. Site Symlink
9. Apache Restart (und collect domains)

# Create a Discord Bot

## JSON

Attributes:

`type: discord_bot`
: The type `discord_bot` sets this project type as a Python project implementing a discord bot.

`hostname: <hostname>.snackbag.net`
: The value of the `hostname` attribute determines the domain name, under which the site will be online.
The domain name has to end with `.snackbag.net`.

`github: "git@github.com:...`
: The URL that holds the content for the site.
It has to start with `git@github.com:`

`deploykey: /pathname`
: The path to a `ssh` deploy keypair.
The name refers to the private key.
The public key must be in the same directory, with the same name + `.pub`.
Both files have to readable for the `deploy` program.

`username`:
: The `username` under which the project runs.

`update_cmd`:
: Usually `/usr/local/bin/pip_and_pull`.

`log_cmd`:
: A tail on the bots syslog file (based on <unixuser>).

`restart_cmd`:
: Usually `/usr/bin/systemctl stop/start <projectdir>.service`.

## Creation Flow

1. Create a user
2. Create ssh config (key, config)
3. Create `/etc/projects` entry.
4. Check out `github` into `/home/user/projectdir` using `deploykey`.
5. Python venv, pip und pull.
6. Create a `/etc/systemd/system/mradmin.service`.
7. `systemctl daemon-reload`, `enable` and `start`.

## Service Template

[Unit]
Description=<projectdir>
After=syslog.target network.target

[Service]
Type=simple
User=<username>
Group=<username>
WorkingDirectory=/home/<username>/<projectdir>
ExecStart=/home/<username>/<projectdir>/venv/bin/python3 /home/<username>/<projectdir>/main.py
Restart=always
EnvironmentFile=/home/<username>/<projectdir>/.env

[Install]
WantedBy=multi-user.target


# Command

manage_project [operation] [project]

operation := show, create, delete
project := project name

create: flags für
  --debug
  --type=static_site,wsgi_site,discord_bot
  --hostname=....snackbag.net
  --github=git@github:...
  --username=str
  --projectdir=pathname_component

delete:

show:
  projects -- alle projekte
  <project> -- ein Projekt, alle Parameter