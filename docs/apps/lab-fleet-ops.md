---
id: lab-fleet-ops
title: "Fleet Setup, Upgrade & Console"
sidebar_position: 6
---

# Fleet Setup, Upgrade, Config & Backup CLI

---

## `lab-setup`

**Engine:** `tools/lib/lab_setup.py`

Server provisioning and Setup Trigger dispatcher.

```bash
lab-setup [-l | --list] [-p | --provision] [-t TARGET] [-a | --all] [-s STEP] [-m {gitea,local}]
```

* Lists or dispatches registered provisioning steps (`system_base_provisioning`, `pull_docker_compose`, etc.) via Gitea Actions (`-m gitea`, default) or local Ansible (`-m local`).

---

## `lab-upgrade`

**Engine:** `tools/lib/lab_upgrade.py`

Multi-distro cluster package upgrade dashboard.

```bash
lab-upgrade [-s | --serial] [-f | --force] [hosts ...]
```

* Auto-selects nodes with pending updates (or targets specified hosts), running parallel dashboard upgrades by default or streaming serial logs with `-s`.

---

## `lab-tools`

**Engine:** `tools/lib/lab_tools.py`

Top-level Curses TUI Operations Console (`tools/lib/core/ui_curses.py`) unifying status dashboards, key rotation, Gitea Actions run inspection (`inspect-run <ID>`), and endpoint revocation. Pass `--plain` or `--no-tui` for non-TTY or scriptable environments.

---

## `lab-backup`

**Engine:** `tools/lib/lab_backup.py`

Cluster backup and shared configuration broadcast suite.

```bash
lab-backup [-a | --all] [-g | --gateway] [-b | --broadcast] [-s SOURCE]
```

* `-g, --gateway`: Backs up gateway firewall and DNS configs.
* `-b, --broadcast`: Collects shared local configs from `-s SOURCE` and broadcasts them across the fleet.
* `-a, --all`: Executes both gateway backup and shared config broadcast.

---

## `lab-config`

**Engine:** `tools/lib/lab_config.py`

Bi-directional GitOps local configuration controller (`/usr/local/etc/openlab/conf/backup.yml`).

```bash
lab-config [--init | --show | --diff | --update | --reset | --restore] [-m MESSAGE]
```

* `--init`: Initializes local config from the remote template.
* `--show` / `--diff`: Inspects local config or diffs against remote repo `HEAD`.
* `--update`: Validates, commits, pushes local edits, and triggers cluster sync.
* `--reset` / `--restore`: Discards local edits to remote `HEAD` or rolls back to `HEAD~1`.

---

## `lab-info`

**Engine:** `tools/lib/lab_info.py`

CMDB hardware & package telemetry suite.

```bash
lab-info [-a | --all] [-d | --dispatch-only] [-p | --pull-only] [-r | --render-only]
```

* Dispatches Gitea Actions audit workflows (`-d`), pulls updated `openlab-configs` (`-p`), and renders Markdown node manuals from `node-information/node_*.json` (`-r`).
