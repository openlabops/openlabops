---
id: fleet-and-ssh
title: Fleet Operations & SSH Lifecycle
sidebar_position: 2
---

# Fleet Operations & SSH Lifecycle CLI

These tools live in `tools/bin/` and run with zero external Python dependencies (`[INV-01]`). Tasks requiring Ansible execution are dispatched remotely to Gitea Actions via `tools/lib/core/gitea_api.py`.

---

## `lab-status`

**Engine:** `tools/lib/lab_status.py`

Real-time cluster health, SSH key status, and `authorized_keys` backdoor auditor.

```bash
lab-status [-q] [-k] [-a] [-n] [-d] [-p HOST] [-b | -t] [--json]
```

* `-q, --quick`: Probe localhost only (skip remote fleet).
* `-k, --keys-only`: Display managed SSH private/agent key status only.
* `-a, --audit-keys`: Deep-audit `authorized_keys` across all nodes against known manifest/secrets fingerprints to detect unauthorized keys.
* `-n, --nodes-only`: Display server nodes and package status only.
* `-p, --probe HOST`: Probe a single host with full diagnostics (`-d` for STDERR/exit code).
* `-b` / `-t` / `--json`: Switch between Box Cards UI, plain table (default), or structured JSON.

---

## `lab-ssh`

**Engine:** `tools/lib/lab_ssh.py`

Central SSH lifecycle manager and 3-phase key rotation dispatcher.

```bash
lab-ssh [-a | --rotate-all] [--rotate-ansible] [--rotate-storage] [--rotate-git]
        [-t TARGET] [-g [HOSTNAME]] [--sync-keys] [--sync-config] [--revoke HOSTNAME]
```

* `--rotate-ansible` / `--rotate-git` / `--rotate-all`: Dispatches Gitea Actions playbooks for 3-phase zero-downtime key rotation.
* `-g [HOSTNAME]`: Generates a per-host endpoint keypair and deploys the public key.
* `--sync-keys` / `--sync-config`: Synchronizes managed keys and standard `~/.ssh/config` host aliases.
* `--revoke HOSTNAME`: Globally revokes a decommissioned endpoint's public key across the fleet.

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

Top-level Curses TUI Operations Console (`tools/lib/core/ui_curses.py`) unifying status dashboards, key rotation, Gitea Actions run inspection (`inspect-run <ID>`), and endpoint revocation. Pass `--plain` / `--no-tui` for non-TTY or scriptable environments.

---

## `lab-boot-sync`

**Engine:** `tools/lib/lab_boot_sync.py`

Endpoint boot public key synchronizer & lockout guard.

```bash
lab-boot-sync [-c | --check] [-f | --force] [-w | --wait] [--timeout SEC]
              [--target-host HOST] [--target-user USER]
```

* Compares local state with remote `openlab-secrets` commit SHA; if stale, triggers key deployment, waits for convergence (`-w`), and writes `/run/openlab/synced_ok` so lockout guards (`tools/lib/core/lockout.py`) can unlock safely.
