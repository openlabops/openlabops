---
id: lab-dev-and-helpers
title: "Dev Setup, Testing & Helpers"
sidebar_position: 7
---

# Development Setup, Testing & Helper Scripts

---

## `lab-dev-setup`

**Script:** `bin/lab-dev-setup`

Declarative workstation bootstrapper invoking `ansible/playbooks/dev-environment.yml`. Ensures `ansible`, `cue`, and `docker` are ready; if `ansible` is missing, automatically creates `.venv` and installs `ansible-core`.

```bash
lab-dev-setup [--check | -c] [--force | -f]
```

---

## `lab-test`

**Script:** `bin/lab-test`

Unified sandbox & acceptance test orchestrator.

```bash
lab-test [-m | --manual] [-a | --auto] [-g | --dagger] [--dr [TARGET]]
         [--kvm [PERSONA]] [-s | --status] [-r | --reset] [-d | --down]
         [-G {standalone,dind,external,local}] [--lang {zh_TW,en_US,ja_JP}]
```

* `-m, --manual`: Starts `mock-console`, `mock-gitea`, and multi-distro containers, then attaches an interactive shell inside `mock-console`.
* `-a, --auto`: Full unattended E2E acceptance (boot → onboard → tool checks → DR drill → teardown).
* `-g, --dagger`: Executes the Dagger DinD verification pipeline (`tests/e2e/test_dagger.py`).
* `--dr [TARGET]`: Runs the SHA-256 disaster recovery drill (`tests/sandbox/dr_drill.sh`).

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
