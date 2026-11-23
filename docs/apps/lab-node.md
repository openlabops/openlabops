---
id: lab-node
title: "Node Onboarding (lab-node)"
sidebar_position: 2
---

# `lab-node` — Dynamic Node Ingestion & Inventory

**Entrypoint:** `bin/lab-node` → `tools/bin/lab-node` → **Engine:** `tools/lib/lab_node.py` & `engine/onboard.py`

`lab-node` manages dynamic node ingestion, removal, listing, and inventory synchronization. It handles PTY-based interactive SSH authentication and extracts OS classification facts without storing raw hardware telemetry in inventory files.

## Synopsis

```bash
lab-node {add,remove,list,sync} [OPTIONS]
```

## Subcommands

* **`add <IP/Host> [--user USER] [--port PORT] [--key FILE]`**:
  Connects to the target host using `execute_pty_ssh()`, streams `engine/bootstrap_probe.sh`, extracts OS family/distribution/role, writes `conf/nodes/<hostname>.json`, and recompiles `ansible/inventory/hosts.yml`.
* **`remove <hostname>`**:
  Archives/removes the node's classification file from `conf/nodes/` and recompiles inventory snapshots.
* **`list`**:
  Displays all currently managed nodes, primary IPs, and assigned roles.
* **`sync`**:
  Re-runs `engine/classifier.py --apply` to recalculate `current.json` and `ansible/inventory/hosts.yml`.

## Key Selection & PTY Execution (`engine/onboard.py`)

`onboard_node()` supports both Day-0 (`lab-init`) and Day-2 (`lab-node add`) workflows:

1. **Ephemeral vs. Permanent Key Priority**:
   * **Day-0 (`ephemeral_pubkey` provided)**: Always prioritizes the ephemeral bootstrap key (`ephemeral_pubkey` + `/tmp/lab_bootstrap_keys/id_ed25519`), even if `~/.ssh/<target_user>.key` already exists on the control machine. Step 5 of `lab-init` subsequently rotates to the permanent key.
   * **Day-2 (`ephemeral_pubkey is None`)**: Uses the existing permanent key (`~/.ssh/<target_user>.key`) and derives its public key dynamically via `ssh-keygen -y -P "" -f` (falling back to `.pub` only if derivation fails).
2. **PTY Human Simulation (`execute_pty_ssh`)**:
   Allocates a real controlling TTY via Python's built-in `pty` module to handle SSH password prompts, `sudo` password prompts, and host key confirmations without external dependencies like `sshpass` or `pexpect` (`[INV-01]`).
3. **Storage Path Resolution (`_get_nodes_dir()`)**:
   * When `LAB_NODES_DIR` or `LAB_INIT_WORK_DIR` is set (during `lab-init`), node JSON files are written to `/tmp/.../conf/nodes/`.
   * During standalone Day-2 operations, node JSON files are persisted in `conf/nodes/<hostname>.json`.
