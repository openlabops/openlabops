---
id: zero-dep-runner-model
title: "Zero-Dependency Stdlib & Act Runner"
sidebar_position: 6
---

# Zero-Dependency Python Stdlib & Gitea Act Runner Model

## `[INV-01]` Zero External Python Dependencies

All control-plane engines (`engine/*.py`) and endpoint CLI tools (`tools/lib/*.py`) run strictly on the Python 3 standard library (`NO pip`, `NO requests`, `NO pyyaml`, `NO paramiko`):

* **YAML Parsing**: `tools/lib/core/yaml_parser.py`
* **Gitea REST API**: `tools/lib/core/gitea_api.py` (built on `urllib.request`)
* **Terminal UI**: `tools/lib/core/ui_curses.py` & `engine/bsd_dialog.py` (built on `curses`)
* **PTY SSH Automation**: `engine/onboard.py` (built on `pty`, `os`, `select`)

This guarantees every `lab-*` CLI works out-of-the-box on minimal Linux distributions without virtualenv drift.

## Centralized Gitea Act Runner Execution

Managed endpoints and operator workstations do **not** need `ansible-core` installed locally:

1. Operator runs `lab-ssh`, `lab-setup`, `lab-upgrade`, or `lab-backup`.
2. The CLI dispatches a `workflow_dispatch` event to `<prefix>-workflows` via Gitea API.
3. The **Gitea Act Runner** container (`ansible-core` pre-installed) checks out `<prefix>-operations` (read-only), `<prefix>-configs`, and `<prefix>-secrets`, and executes the stateless Ansible playbook over SSH.
