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

`deploykey: "ssh-rsa ...."`
: The path to a `ssh` deploy keypair.
The name refers to the private key.
The public key must be in the same directory, with the same name + `.pub`.
Both files have to readable for the `deploy` program.

The values for the following variables are not specified in the project file and are implied:

`projectdir:`
: `/var/www/<hostname>`

`username` and `userid`:
: All content is owned by the user `content`.

`update_cmd` and `log_cmd`:
: Standard `git pull --rebase` and an `tail -F /var/log/httpd/{access,error}.log`.

`restart_cmd`:
: none needed.

## Creation Flow

Invariants:

- hostname must not exist.
- Implied values must not be specified
  (projectdir, username, userid, update_cmd, log_cmd and restart_cmd).

0. Create `/etc/projects` entry.
1. Check out `github` into `projectdir` using `deploykey` as `content`.
2. Create apache config.
3. Run `collect_domains`

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

`username` and `userid`:
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
- userid must not exist.
- username must not exist.

Also, the deploykey must be set for the github repository in order for the initial checkout to work.

0. Create `/etc/projects` entry.
1. `useradd -u <userid> -m -c "<projectdir> Webserver" <username>
2. `passwd -l <username>`
3. `mkdir /home/<username>/.ssh` + user + permissions
4. `su -l -c "ssh-keygen -t rsa -b 4096 -N "" -f /home/<username>/.ssh/id_deploykey - <username>`
5. Deploykey anzeigen + Bestätigung abwarten (github update)
6. `su -l -c "git clone <github> /home/<username>/<project> - <username>`
7. `mkdir /var/www/<hostname>` + index.html + owner content
8. `su -l -c "/usr/local/bin/pip_and_pull"` zum Anlegen des venv, installieren der requirements und git pull.
9. Erzeugen der `/etc/httpd/conf.sites.d/<hostname>`.
10. Double restart_apache

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

`username` and `userid`:
: The `username` under which the project runs.

`projectdir`:
: Subdirectory in the users home, so `/home/<username>/<projectdir>`.

`update_cmd`:
: Usually `/usr/local/bin/pip_and_pull`.

`log_cmd`:
: A tail on the bots syslog file (based on <unixuser>).

`restart_cmd`:
: Usually `/usr/bin/systemctl stop/start <projectdir>.service`.

## Creation Flow

0. Create `/etc/projects` file.
1. `useradd -u <userid> -m -c "<projectdir> Webserver" <username>
2. `passwd -l <username>`
3. `mkdir /home/<username>/.ssh` + user + permissions
4. `su -l -c "ssh-keygen -t rsa -b 4096 -N "" -f /home/<username>/.ssh/id_deploykey - <username>`
5. Deploykey anzeigen + Bestätigung abwarten (github update)
6. `su -l -c "git clone <github> /home/<username>/<project> - <username>`
7. Create `/home/<username>/<projectdir>/.env`.
7. Create a `/etc/systemd/system/mradmin.service`.
8. `systemctl daemon-reload`, `enable` and `start`.

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
  --type=static_site,wsgi_site,discord_bot
  --hostname=....snackbag.net
  --github=git@github:...
  --deploykey=path
  --username=str
  --projectdir=pathname_component

delete:

show:
  projects -- alle projekte
  <project> -- ein Projekt, alle Parameter