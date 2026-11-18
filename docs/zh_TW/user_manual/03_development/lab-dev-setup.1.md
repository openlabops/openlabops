# lab-DEV-SETUP(1) - AI Agent & Developer Workspace Bootstrapper

## NAME
`lab-dev-setup` - Zero-Touch Developer Environment & Toolchain Provisioner

## 類別 (CATEGORY)
> **[開發、測試與 IaC 維護 (Development, Testing & IaC)]**

## SYNOPSIS
```bash
./bin/lab-dev-setup [OPTIONS]
```

## DESCRIPTION
`lab-dev-setup` automates the local development workstation setup for both human developers and AI coding agents (Antigravity, Cursor, Claude Code). It checks for and installs required toolchains (`ansible`, `cue`, `docker`, `agy`), setting up an isolated virtual environment (`.venv`) with `ansible-core` if the host OS lacks Ansible. It then invokes `ansible/playbooks/dev-environment.yml` for complete idempotency.

## OPTIONS
- `--check`    : Dry-run check for required toolchains and exit without modifying environment.
- `--force`    : Recreate virtual environment and force toolchain bootstrap.
- `--help, -h` : Display usage summary.

## EXAMPLES
```bash
# Bootstrap developer environment:
./bin/lab-dev-setup

# Check prerequisite status:
./bin/lab-dev-setup --check
```

