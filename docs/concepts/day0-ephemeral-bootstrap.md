---
id: day0-ephemeral-bootstrap
title: "Day-0 Ephemeral Bootstrap & /tmp Isolation"
sidebar_position: 2
---

# Day-0 Ephemeral Bootstrap & `/tmp` Workspace Isolation

## Why `/tmp` Isolation Matters

Running `lab-init` in the incubator repository directly would otherwise overwrite tracked template files (`conf/openlab.manifest.yml`, `ansible/group_vars/all.yml`, `tools/conf/tools.config.json`) and leave node JSON files behind.

To keep the incubator repository clean:

1. **`LAB_INIT_WORK_DIR` (`/tmp/lab_init_work_*`)**:
   `engine/initialize.py` creates a temporary workspace in `/tmp` at startup and registers `atexit` cleanup.
   * `engine/onboard.py` (`_get_nodes_dir()`) and `engine/classifier.py` detect `LAB_INIT_WORK_DIR` and write `conf/nodes/*.json`, `current.json`, and `ansible/inventory/hosts.yml` into `/tmp`.
   * `export_site_manifest()` writes the site manifest into `/tmp`, and `engine/compiler.py` compiles downstream repositories into `/tmp/.../compiled` (without `--ops-internal`).
   * `push_fresh_configs_and_secrets_to_gitea()` pushes the compiled `/tmp` artifacts directly to Gitea `configs` and `secrets`.
2. **Ephemeral Bootstrap Key (`/tmp/lab_bootstrap_keys/`)**:
   * Generated in `/tmp` with **no `from="..."` IP restriction** (`[INV-02]`), never written to `~/.ssh/`.
   * During Day-0, `onboard_node()` prioritizes `ephemeral_pubkey` even if `~/.ssh/<target_user>.key` already exists on the workstation.
3. **PTY Human Simulation (`execute_pty_ssh`)**:
   Uses Python's built-in `pty` module to allocate a real controlling TTY for SSH/sudo password prompts without external dependencies (`sshpass` or `pexpect`).
4. **Rate-Limit Backoff (`_run_ssh_with_backoff`)**:
   Retries transient SSH handshake failures (`kex_exchange_identification`, `Connection reset by peer`, `Connection timed out`) with progressive backoff to prevent `MaxStartups` or firewall rate-limit drops.
