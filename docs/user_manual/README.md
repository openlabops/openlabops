# OpenLabOps User Manual (`docs/user_manual/`)

> **Language / 語言 / 言語**: **English** | [繁體中文](../zh_TW/user_manual/README.md) | [日本語](../ja/user_manual/README.md)

The user manual is organized into three subdirectories by operational phase and can be browsed interactively in the terminal via `./bin/lab-man` or `./bin/lab-tools`:

---

## 1. Installation & Onboarding ([`01_installation/`](01_installation/))
> Day-0 cluster bootstrap, local Gitea setup, live hardware probing, and dynamic node onboarding.

- [`lab-init(1)`](01_installation/lab-init.1.md) — Day-0 cluster initialization wizard
- [`lab-node(1)`](01_installation/lab-node.1.md) — Dynamic node onboarding & configuration tool
- [`lab-discover(1)`](01_installation/lab-discover.1.md) — Live hardware & SSH key telemetry probe

## 2. Post-Installation Operational Apps ([`02_operations/`](02_operations/))
> Daily cluster operations: health dashboard, SSH key rotation, backups, dotfiles, and package upgrades.

- [`lab-status(1)`](02_operations/lab-status.1.md) — Real-time cluster status dashboard & zero-trust key audit
- [`lab-ssh(1)`](02_operations/lab-ssh.1.md) — Smart SSH launcher & 4-stage key rotation
- [`lab-setup(1)`](02_operations/lab-setup.1.md) — Server baseline setup & container environment mounting
- [`lab-backup(1)`](02_operations/lab-backup.1.md) — Declarative node backup & disaster recovery
- [`lab-config(1)`](02_operations/lab-config.1.md) — Local dotfiles & shell environment manager
- [`lab-upgrade(1)`](02_operations/lab-upgrade.1.md) — Parallel multi-node package upgrade tool
- [`lab-info(1)`](02_operations/lab-info.1.md) — Node telemetry inspection & Markdown doc generator
- [`lab-tools(1)`](02_operations/lab-tools.1.md) — Interactive operations TUI console
- [`lab-apply(1)`](02_operations/lab-apply.1.md) — Declarative template compiler & config sync
- [`lab-diff(1)`](02_operations/lab-diff.1.md) — Configuration drift inspector

## 3. Development & Test Console ([`03_development/`](03_development/))
> Developer workstation bootstrap, multi-distro container sandbox, and terminal manual browser.

- [`lab-dev-setup(1)`](03_development/lab-dev-setup.1.md) — Developer & AI workspace bootstrapper
- [`lab-test(1)`](03_development/lab-test.1.md) — Multi-distro sandbox & integration test engine
- [`lab-man(1)`](03_development/lab-man.1.md) — Interactive terminal manual browser
