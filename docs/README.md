# OpenLabOps Operations Engine Documentation Hub (`docs/`)

> **Language / 語言 / 言語**: **English** (Default) | [繁體中文](zh_TW/README.md) | [日本語](ja/README.md)

> This directory centralizes all program specifications and user manuals for the OpenLabOps Operations Engine.  
> Organized strictly by responsibility, with all configuration parameters aligned to `conf/`.

---

## Documentation Taxonomy

This documentation hub is divided into two main sections:
1. **[Program & Architecture Documentation](#1-program--architecture-documentation)**: System invariants, architecture specs, Ansible IaC, CLI core libraries, CI/CD workflows, and SSH key security specs.
2. **[User Manual (`docs/user_manual/`)](#2-user-manual)**: Man-page style operational manuals for installation, daily operations, and development/testing.

---

## 1. Program & Architecture Documentation

### 1. Architecture & Specifications (`architecture/`)
* [Code + Config Separation Plan](architecture/code-config-separation-plan.md)
* [Incubator & Initialization Specification](architecture/incubator-and-initialization-spec.md)
* [Federation Synthesis & Distillation Specification](architecture/federation-synthesis-spec.md)
* [Dagger / Sandbox Testing Environment Specification](architecture/dagger-testing-environment-spec.md)
* [Template Compiler & Neutral Roles Specification](architecture/template-compiler-and-neutral-roles.md)
* [Playbook Parameterized Abstraction Specification](architecture/playbook-parameterized-abstraction-spec.md)
* [Master Invocation Matrix: Tools CLI/API → Workflows → Playbooks](architecture/tools-workflow-playbook-mapping.md)
* [Ansible IaC Architecture Guide](architecture/ansible-architecture.md)
* [CLI Tools Architecture Guide](architecture/tools-architecture.md)
* [Package Information Management Specification](architecture/package-information-spec.md)
* [Node Onboarding & Ingestion Specification](architecture/node-onboarding-and-ingestion-spec.md)

### 2. Security, SSH Keys & Secrets (`security/`)
* [SSH Keys & Secure Connectivity Specification (SSOT)](security/ssh-keys-spec.md)
* [CI/CD Action Secrets & Permission Boundaries](security/action-secrets-spec.md)
* [Workflow Key Mapping Topology](security/ssh-key-mapping.md)

### 3. Ansible IaC Automation (`ansible/`)
* [Ansible Modules & Playbooks Overview](ansible/README.md)
* [Roles Modularization Specification](ansible/roles-modularization-spec.md)
* [Inventory Topology & Auto-Classification](ansible/inventory.md)
* [Custom Package Facts Module](ansible/custom-package-facts.md)
* **Playbooks (`ansible/playbooks/`)**:
  * [Playbooks Orchestration Overview](ansible/playbooks/playbooks-overview.md)
  * [Node Provisioning Playbook](ansible/playbooks/node-provisioning.md)
  * [Endpoint Bootstrap Playbook](ansible/playbooks/endpoint-bootstrap.md)
  * [Dotfiles Deployment Playbook](ansible/playbooks/dotfiles-deployment.md)
  * [Package Management Playbook](ansible/playbooks/package-management.md)
* **Audit Scripts (`ansible/scripts/`)**:
  * [Linux Node Audit Script](ansible/scripts/audit-nodes.md)
  * [Host Package Vars Sync Script](ansible/scripts/sync-host-package-vars.md)

### 4. Python CLI Toolchain (`tools/`)
* [CLI Toolchain Overview](tools/README.md)
* [Development Roadmap (TODO)](tools/todo.md)
* [Versioning Specification](tools/versioning-spec.md)
* [Installation & Zero-Dependency Python Spec](tools/installation-spec.md)
* [Curses TUI Specification](tools/curses-tui-spec.md)
* [SSH Tools Integration Guide](tools/ssh-tools-integration.md)
* **Operational CLI Commands**:
  * [`lab-tools` Cluster Console](tools/lab-tools.md)
  * [`lab-status` Cluster Dashboard](tools/lab-status.md)
  * [`lab-ssh` Interactive SSH Selector](tools/lab-ssh.md)
  * [`lab-info` Node Telemetry Inspector](tools/lab-info.md)
  * [`lab-backup` Declarative Backup Tool](tools/lab-backup.md)
  * [`lab-setup` Environment Initializer](tools/lab-setup.md)
  * [`lab-upgrade` Multi-Node Package Upgrader](tools/lab-upgrade.md)
  * [`endpoint-ssh-tools` External Endpoint Tools](tools/endpoint-ssh-tools.md)
  * [`lab-node` Dynamic Node Onboarding](tools/lab-node.md)
* **Core Libraries (`tools/core/`)**:
  * [Global Config & Node Discovery](tools/core/config.md)
  * [Live Probe Core](tools/core/live-probe.md)
  * [TUI Menu Engine](tools/core/ui-menu.md)
  * [TUI Theme & Colors](tools/core/ui-theme.md)
  * [Gitea REST API Client](tools/core/gitea-api.md)
  * [Versioning & Update Core](tools/core/version.md)
  * [Markdown Node Doc Renderer](tools/core/render-node-doc.md)

### 5. Gitea Actions CI/CD (`workflows/`)
* [CI/CD Workflow Design Guide](workflows/README.md)
* [Workflow Architecture & Schedules](workflows/workflows-guide.md)
* [Package Inventory Sync Workflow](workflows/sync-package-inventory.md)
* [Post-Push Trigger Script](workflows/post-push-trigger.md)

---

## 2. User Manual

User manuals are maintained in [`docs/user_manual/`](user_manual/README.md) in standard Linux man-page style and can be browsed interactively via `./bin/lab-man`:

### 1. Installation & Onboarding (`user_manual/01_installation/`)
* [`lab-init(1)`](user_manual/01_installation/lab-init.1.md): Day-0 cluster bootstrap, repository initialization, and key rotation wizard
* [`lab-node(1)`](user_manual/01_installation/lab-node.1.md): Dynamic node onboarding, live PTY probing, and classification wizard
* [`lab-discover(1)`](user_manual/01_installation/lab-discover.1.md): Cluster-wide hardware facts and SSH key audit probe

### 2. Operations & Maintenance (`user_manual/02_operations/`)
* [`lab-status(1)`](user_manual/02_operations/lab-status.1.md): Cluster health, 90-day key age, and authorized_keys audit dashboard
* [`lab-ssh(1)`](user_manual/02_operations/lab-ssh.1.md): Interactive SSH selector with environment detection
* [`lab-info(1)`](user_manual/02_operations/lab-info.1.md): Single-node telemetry detail card viewer
* [`lab-backup(1)`](user_manual/02_operations/lab-backup.1.md): Declarative configuration backup and GitOps sync
* [`lab-upgrade(1)`](user_manual/02_operations/lab-upgrade.1.md): Multi-threaded, multi-distro package upgrade dashboard
* [`lab-config(1)`](user_manual/02_operations/lab-config.1.md): Local dotfiles and GitOps configuration sync
* [`lab-diff(1)`](user_manual/02_operations/lab-diff.1.md): Manifest-to-rendered-output drift inspector
* [`lab-apply(1)`](user_manual/02_operations/lab-apply.1.md): Compile declarative intent into downstream inventory and configs
* [`lab-tools(1)`](user_manual/02_operations/lab-tools.1.md): Toolchain version check and sync manager

### 3. Development & Testing (`user_manual/03_development/`)
* [`lab-dev-setup(1)`](user_manual/03_development/lab-dev-setup.1.md): One-click developer workstation environment setup
* [`lab-test(1)`](user_manual/03_development/lab-test.1.md): Multi-distro Linux sandbox and end-to-end test console
* [`lab-man(1)`](user_manual/03_development/lab-man.1.md): Interactive terminal manual browser
