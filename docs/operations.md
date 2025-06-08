# What we do

## Static Site

```bash
./deploy.py create mysite --type static_site \
  --hostname mysite.snackbag.net \
  --github git@github.com:username/mysite.git \
  --username myuser \
  --projectdir www
```

This assumes:

- The project name is mysite.
- The site will be hosted at mysite.snackbag.net.
- The git repo is located at git@github.com:username/mysite.git.
- The system user myuser will be created.
- The site's content is in the www subdirectory of the user's home.

Create UNIX User
: A new system user (`myuser`) is created to own the deployment.

Generate SSH Key
: A deploy SSH key (`id_deploykey`) is generated and configured to authenticate against GitHub.

Clone Git Repo
: The program clones the specified GitHub repository into `/home/myuser/www`.

Create Project Config File
: A JSON file representing the project is saved in `/etc/projects/mysite`.

Create Apache Config
: An Apache `Use VHost` configuration is written to serve the static site under the specified hostname.

Create Web Symlink
: A symbolic link is created from `/var/www/mysite.snackbag.net` to `/home/myuser/www`.

Restart Apache
: Apache (`httpd`) is restarted (twice) to pick up the new site and SSL domain configuration.

Print Deploy Instructions
: The public SSH key is displayed with instructions to add it to GitHub as a deploy key.
  The key is also saved to `/home/myuser/.ssh/id_deploykey.pub`.

## Redirect Site

```bash
./deploy.py create coolredirect --type redirect_site \
  --hostname cool.snackbag.net \
  --to-hostname target.example.com
```

This assumes:
- The redirect project is named coolredirect.
- The site should redirect from cool.snackbag.net to target.example.com.

Create Project Config File
: Saves a JSON config for `coolredirect` in `/etc/projects/coolredirect`, 
  including the source and destination hostnames.

Create Apache Config
: Writes a `use RedirectVHost` Apache configuration file at `/etc/httpd/conf.sites.d/cool.snackbag.net.conf`, 
  instructing Apache to redirect traffic.

Restart Apache
: Restarts Apache (`httpd`) twice to load the new config and ensure SSL certificates are handled correctly.

## WSGI Site

```bash
./deploy.py create myapp --type wsgi_site \
  --hostname myapp.snackbag.net \
  --github git@github.com:username/myapp.git \
  --username myuser \
  --projectdir appdir
```

This assumes:
- The project name is `myapp`.
- The site will be hosted at `myapp.snackbag.net`.
- The GitHub repo is located at `git@github.com:username/myapp.git`.
- The deployment user will be `myuser`.
- The application code lives in `/home/myuser/appdir`.

Ideally, project name, site name, github repo, user and appdir are all `myapp`.

Create UNIX User
: A new system user `myuser` is created with a home directory.

Generate SSH Key
: An SSH deploy key is generated and placed in `/home/myuser/.ssh/id_deploykey`.

Clone Git Repo
: Clones the GitHub repository to `/home/myuser/appdir`. 
  Adjusts ownership of all files to myuser.

Set Up Python Environment
: Creates a `venv` in the project directory.
  Installs `pip`, `wheel`, and all requirements from `requirements.txt`.
  Creates an empty `.env` file.  

Write Project File
: Saves the configuration to `/etc/projects/myapp` as JSON.

Create Apache Config
: Writes a `use PyApp` Apache config for `myapp.snackbag.net`. 
  Links it to the correct app directory and UNIX user.

Create Site Symlink
: Symlinks `/var/www/myapp.snackbag.net` to `/home/myuser/appdir` for consistency or optional static file serving.

Restart Apache
: Restarts Apache twice to activate the new configuration and ensure SSL domains are registered.

Print Instructions
:Displays a banner with the deploy public key and GitHub link to add it as a deploy key.

## Discord Bot

Assumes a bot written in Python.

```bash
./deploy.py create botfriend --type discord_bot \
  --github git@github.com:username/botfriend.git \
  --username botuser \
  --projectdir botcode
```

This assumes:
- The bot project is named botfriend.
- The code lives in the `botcode` subdirectory under `/home/botuser`.
- The bot is hosted in a private GitHub repo using a deploy key.

Create UNIX User
: Adds a new system user `botuser` with a home directory.

Generate SSH Key
: Creates a private/public deploy key pair in `/home/botuser/.ssh`.

Clone Git Repo
: Clones `git@github.com:username/botfriend.git` into `/home/botuser/botcode`. 
  Changes file ownership to `botuser`.

Set Up Python Environment
: Creates a virtual environment in the project directory.
  Installs `pip`, `wheel`, and dependencies from `requirements.txt`.
  Creates an empty `.env` file.

Write Project File
:Saves configuration info to `/etc/projects/botfriend`.

Create `systemd` Service
: Writes a service file at `/etc/systemd/system/botfriend.service`.
  Configures it to run the bot via the virtual environment (e.g. `venv/bin/python3 main.py`).
  Loads environment from `.env`.

Enable and Start Service
: Reloads `systemd`, enables the bot service, and starts it.

Set Up Logging
: Configures rsyslog to capture logs into `/var/log/services/botfriend.log`.
  Ensures logs rotate daily and are stored securely.

Print Instructions
: Displays the public SSH key and link to GitHub deploy key setup.

A discord_bot deployment automates setting up a user, environment, code checkout,
and persistent service via systemd, with full log management.
The result is a self-managed bot that survives reboots 
and can be updated later with a simple `deploy.py update botfriend`.

## Go Site

```bash
./deploy.py create wiki \
  --type go_site \
  --hostname wiki.snackbag.net \
  --github git@github.com:snackbag/wiki.git \
  --username wiki \
  --projectdir wiki \
  --port 3001
```

Most of these parameters are optional, we need a hostname, a port, a username and a github.

Create UNIX User
: Adds a system user `wiki` with a home directory.

Generate SSH Deploy Key
: Creates a key pair in `/home/wiki/.ssh`.

Clone Git Repo
: Clones `git@github.com:snackbag/wiki.git` into `/home/wiki/wiki`.

Build Go Project
: Runs `make` in the repo directory, expecting it to build a binary named `wiki`.

Write Project Config File
: Saves details to `/etc/projects/wiki`.

Create systemd Service
: Writes a `systemd` service file to launch the binary as `ExecStart=/home/wiki/wiki/wiki`.
  Ensures it restarts on failure and loads environment from an `.env` file.

Enable and Start Service
: Reloads `systemd`, enables the service, and starts it immediately.

Configure Syslog Logging
: Routes all service logs to `/var/log/services/wiki.log`.
  Sets up daily log rotation.

Create Apache Proxy Config
: Writes a `use ProxyVHost` config to forward HTTP traffic from wiki.snackbag.net to localhost:3001.

Restart Apache
: Restarts the Apache server twice to update host/domain and SSL settings.

Print Instructions
: Shows the deploy key and GitHub settings URL so you can finish setup.

A go_site deployment builds and runs your Go web service under `systemd`, 
sets up Apache to reverse proxy to it, and manages logging and startup. 
Once deployed, the service can be updated, restarted, or removed entirely using this tool.

## Proxy

```bash
./deploy.py create dashproxy --type proxy \
  --hostname dashboard.snackbag.net \
  --port 3000
```

Write Project Config File
: Saves a JSON file to /etc/projects/dashproxy describing the proxy setup.

Create Apache Proxy Config
: Writes a `use ProxyVHost` configuration to `/etc/httpd/conf.sites.d/dashboard.snackbag.net.conf`.
  Instructs Apache to forward traffic from `dashboard.snackbag.net` to `localhost:3000`.

Restart Apache
: Restarts the Apache service twice to apply new configuration and ensure proper certificate handling for the domain.

# Why do we restart Apache twice?

We are using `mod_md` to manage SSL certificates.  The first restart is to
update the host/domain settings and obtain a certificate.
The second restart actually loads the SSL certificate into Apache.

Strictly speaking, we only need the double restart when the list of SSL domain name changes, a site is added or removed.
In practice it is fast enough that we always to it this way.

# Other operations

The other operations, `logs`, `update`, `stop`, `start`, `restart`, are also special-cased for the service type.

The `delete` operation does the necessary operations in reverse, 

- stop systemd service, 
- stop apache, 
- remove log config, 
- remove systemd serivce
- remove apache config
- delete the user
- and finally delete the project file,

with a bit of special casing.
Overall deletion is relatively simple because most files are in the user home, 
so when we delete the user, we also delete all local config.

All things will be kept in the `restic` backup, so they can be undone to some extent.

# Global Options: Debug, Dry Run, Timeout

The program defines the following global flags, which can be used with any command:

##  -d, --debug (default: 0)

Type
: Repeatable flag

Purpose
: Enables debug output. More `-d` = more detail (3 times should be enough)

- `-d`: Basic debug info
- `-dd`: Include subprocess calls and file ops
- `-ddd`: also include system-level restarts

# -n, --dry-run (default: False)

Type
: Boolean flag

Purpose
: Simulates actions without making any actual changes.

With `--dry-run`, commands like `useradd`, file writes, Git operations, and restarts are skipped,
but printed as if they would have run.

# -t, --timeout (default: 30 sec)

Type
: Integer (default: 30)

Purpose
: Sets a timeout for subprocess commands like git clone or pip install.

It is suggested that you place global options immediately after the `deploy` command:

```bash
./deploy.py -d -n -t 60 create mysite --type static_site --github ...
```
