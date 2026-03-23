# Notes

## Remote Host

- Approved SSH target: `codex@192.168.1.10` using key `./.ssh/codex`
- Remote hostname: `server`
- Approved command prefixes:
  - `ssh -i ./.ssh/codex codex@192.168.1.10`
  - `ssh -t -i ./.ssh/codex codex@192.168.1.10`
  - `scp -i ./.ssh/codex`
  - `rsync -e "ssh -i ./.ssh/codex"`

## Machine Summary

- OS: Rocky Linux 9.7
- Kernel: `5.14.0-611.16.1.el9_7.x86_64`
- CPU: AMD Ryzen 7 5700G, 8 cores / 16 threads
- Memory: 121 GiB RAM
- Swap: 43 GiB

## Storage Layout

- HDD pool: bulk storage and backups
  - Mounted under `/backup`, `/backup/minebackup`, `/export/tm_kk`, `/export/tm_joram_mini`, `/export/tm_mini`, `/export/tm_aircat`, `/export/hassbackup`
- SATA SSD pool: faster shared data/app content
  - Mounted under `/export/video`, `/export/music`, `/export/book`, `/export/comic`, `/export/audiobook`, `/export/webserver`, `/export/disk_images`
- NVMe: OS and performance-sensitive local storage
  - Mounted under `/`, `/boot`, `/boot/efi`, `/home`, `/var/lib/mysql`, `/export/build`

## Active Roles

- File server: Samba and NFS are running
- Web/app server: Apache `httpd` is running on ports 80/443
- Database server: MySQL is running
- Network services: DHCP and DNS-related services are running
- Containers: rootless Podman workloads are present
- VM: libvirt/QEMU is present; a `hass` VM was observed

## Deploy Tool

- `/usr/local/bin/deploy` on the remote host is a symlink to `/root/Source/deploy/deploy`
- A readable copy was placed at `/home/codex/deploy`, then moved into Git at `/home/codex/Source/deploy/deploy`
- Remote Git repo created at `/home/codex/Source/deploy`
- Import commit: `efd12ce` with message `Import deploy script`
- Refactor constraints:
  - target runtime is `uv` with `--managed-python`, not the system Python
  - preferred CLI shape is `uv run --managed-python deploy create <type> <name> ...`
  - create-time options should be type-specific, not one shared option bag
  - Python style preferences: `dataclasses`, `pathlib`, and `httpx` if HTTP is needed
  - project tooling preferences: `pytest`, `ty`, and `ruff`

## /etc/projects

- `/etc/projects` is a directory of per-project JSON files
- Confirmed entries:
  - `grafana`: proxy to port 3000
  - `immich`: proxy to port 2283
  - `navidrome`: proxy to port 4533
  - `plik`: proxy to port 8084
  - `webauthn`: WSGI app from `/home/webauthn/webauthn`

## Apache Config Generation

- `deploy` reads project JSON from `/etc/projects/<project>`
- `deploy` writes Apache snippets to `/etc/httpd/conf.sites.d/<hostname>.conf`
- Confirmed generated forms:
  - `Use ProxyVHost <hostname> <port>`
  - `Use PyApp <hostname> <project> <appdir> <unixuser> <unixgroup>`
  - `Use VHost <hostname>`
  - `Use RedirectVHost <hostname> <to_hostname>`
