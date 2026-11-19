---
id: ops-and-helpers
title: Config, Backup & Helper Tools
sidebar_position: 3
---

# Configuration, Backup & Helper CLI

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

Bi-directional GitOps local configuration controller (`/usr/local/etc` / `backup.yml`).

```bash
lab-config [--init | --show | --diff | --update | --reset | --restore] [-m MESSAGE]
```

* `--init`: Initializes local config from the remote template.
* `--show` / `--diff`: Inspects local config or diffs against remote repo HEAD.
* `--update`: Validates, commits, pushes local edits, and triggers cluster sync.
* `--reset` / `--restore`: Discards local edits to remote HEAD or rolls back to `HEAD~1`.

---

## `lab-info`

**Engine:** `tools/lib/lab_info.py`

CMDB hardware & package telemetry suite.

```bash
lab-info [-a | --all] [-d | --dispatch-only] [-p | --pull-only] [-r | --render-only]
```

* Dispatches Gitea Actions audit workflows (`-d`), pulls updated `openlab-configs` (`-p`), and renders Markdown node manuals from `node-information/node_*.json` (`-r`).

---

## `lab-man`

**Script:** `tools/bin/lab-man` (`bin/lab-man` symlink)

Built-in terminal manual viewer for any `lab-*` command (`lab-man status`, `lab-man init`, etc.).

---

## Standalone Helper Scripts (`tools/bin/`)

| Script | Engine | Purpose |
| :--- | :--- | :--- |
| **`sync-ops-tools`** | `tools/lib/sync_ops_tools.py` | Checks version and deploys/updates `openlabops` CLI tools across target nodes (`-c`, `-f`, `-l`). |
| **`sync-ssh-config`** | `tools/lib/sync_ssh_config.py` | Renders and synchronizes standardized `~/.ssh/config` host aliases (`-p openlab \| endpoint`). |
| **`sync-ssh-keys`** | `tools/lib/sync_ssh_keys.py` | Deploys and fixes permissions on managed SSH keys via Gitea Runner (`-n`, `-u`, `-k`). |
| **`generate-host-ssh-key`** | `tools/lib/generate_host_ssh_key.py` | Generates per-endpoint Ed25519 keypairs (`-H HOSTNAME`) and dispatches public key deployment. |
| **`revoke-host-ssh-key`** | `tools/lib/revoke_host_ssh_key.py` | Revokes an endpoint's public key across all nodes (`-H HOSTNAME`, `--keep-secrets`, `-l`, `-y`). |
| **`render-node-doc`** | `tools/lib/render_node_doc.py` | Renders `node_*.json` CMDB telemetry files into human-readable Markdown manuals (`-o` / `-d`). |
