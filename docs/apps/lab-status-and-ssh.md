---
id: lab-status-and-ssh
title: "Cluster Health & SSH Lifecycle"
sidebar_position: 5
---

# Cluster Health & SSH Lifecycle CLI

These tools live in `tools/bin/` and run with zero external Python dependencies (`[INV-01]`). Remote Ansible operations are dispatched to Gitea Actions via `tools/lib/core/gitea_api.py`.

---

## `lab-status`

**Engine:** `tools/lib/lab_status.py`

Real-time cluster health probe, SSH key status check, and `authorized_keys` backdoor auditor.

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

Central SSH lifecycle manager and 3-phase zero-downtime key rotation dispatcher.

```bash
lab-ssh [-a | --rotate-all] [--rotate-ansible] [--rotate-storage] [--rotate-git]
        [-t TARGET] [-g [HOSTNAME]] [--sync-keys] [--sync-config] [--revoke HOSTNAME]
```

* `--rotate-ansible` / `--rotate-git` / `--rotate-all`: Dispatches Gitea Actions playbooks (`rotate-ansible-keys.yml`, `rotate-git-keys.yml`) for 3-phase rotation (Add new key → Verify new key → Remove old key).
* `-g [HOSTNAME]`: Generates a per-host endpoint Ed25519 keypair and deploys the public key.
* `--sync-keys` / `--sync-config`: Synchronizes managed keys and standardized `~/.ssh/config` host aliases.
* `--revoke HOSTNAME`: Globally revokes a decommissioned endpoint's public key across the fleet.

---

## `lab-boot-sync`

**Engine:** `tools/lib/lab_boot_sync.py` & `tools/lib/core/lockout.py`

Endpoint boot public key synchronizer and lockout guard.

```bash
lab-boot-sync [-c | --check] [-f | --force] [-w | --wait] [--timeout SEC]
              [--target-host HOST] [--target-user USER]
```

* Compares local state with remote `openlab-secrets` commit SHA.
* If stale, dispatches public key deployment, waits for convergence (`-w`), and writes `/run/openlab/synced_ok` so lockout guards (`tools/lib/core/lockout.py`) can unlock safely without locking out the operator.
