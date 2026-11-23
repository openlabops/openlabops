# OpenLabOps: Zero-Dependency Declarative Homelab Operations Framework

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero%20(stdlib%20only)-success.svg)](#invariants)
[![Architecture: Flat LAN](https://img.shields.io/badge/network-flat__lan%20(192.168.1.0%2F24)-orange.svg)](#architecture)
[![Documentation: Wiki](https://img.shields.io/badge/docs-Docusaurus%20Wiki-blueviolet.svg)](https://openlabops.github.io/openlabops/)

**OpenLabOps** is an open-source, turnkey operations control hub and GitOps management framework for modern homelabs and private servers. Built with **100% standard library Python** and stateless Ansible playbooks, it delivers automated node onboarding, three-phase zero-downtime SSH key rotation, sensory hardware discovery, and declarative GitOps synchronization without third-party Python dependencies (`NO pip`, `NO requests`, `NO pyyaml`).

📖 **Full Documentation (EN / 繁體中文 / 日本語):** [OpenLabOps Wiki](https://openlabops.github.io/openlabops/)

---

## 🏗️ Architecture

OpenLabOps separates immutable framework contracts, declarative site intent, and live node telemetry across a 4-repository GitOps federation with blast-radius token isolation.

```mermaid
flowchart TB
    subgraph Console["Control Workstation (~/.ssh Agent)"]
        CLI["Zero-Dependency Python CLI<br/>lab-init / lab-node / lab-status / lab-tools"]
        T1["Tier 1: Core Specs<br/>conf/core.manifest.yml + schema/*.cue"]
        T2["Tier 2: Site Intent<br/>conf/openlab.manifest.yml"]
        T3["Tier 3: Node Telemetry<br/>conf/nodes/*.json"]
    end

    subgraph Federation["4-Repo GitOps Federation"]
        OPS["openlab-operations<br/>Playbooks + Framework"]
        WF["openlab-workflows<br/>CI/CD + Runner Dispatch"]
        CFG["openlab-configs<br/>CMDB + Node Facts"]
        SEC["openlab-secrets<br/>Encrypted Vault + Public Keys"]
    end

    subgraph Fleet["Managed Flat LAN Fleet (192.168.1.0/24)"]
        N1["Server Nodes<br/>Arch / Debian / Ubuntu"]
        N2["Dev & Desktop Nodes<br/>Workstations + Boot Sync Guard"]
        N3["Appliances & Containers<br/>Alpine / Photon / Docker"]
    end

    CLI --> T1 & T2 & T3
    T3 -->|"Compile hosts.yml"| OPS
    CLI -->|"Dispatch Workflow (ci-bot)"| WF
    WF -->|"Read-Only Checkout"| OPS
    WF -->|"Push Telemetry & Facts"| CFG
    WF -->|"Read Key Policies"| SEC
    WF -->|"Ansible Playbooks over SSH"| Fleet
```

### Three-Phase Zero-Downtime Key Rotation

```mermaid
sequenceDiagram
    participant C as Control Station
    participant N as Managed Nodes
    Note over C,N: Stage 1 - Dual-Key Coexistence
    C->>N: Deploy new public key alongside old key
    Note over C,N: Stage 2 - Connectivity Verification
    C->>N: Verify SSH login with new private key
    Note over C,N: Stage 3 - Old Key Revocation
    C->>N: Remove deprecated public key from authorized_keys
```

### Boot-Time Stale Key Auto-Sync & Lockout Guard (`lab-boot-sync`)

Offline or intermittent nodes (workstations, laptops) that missed a key rotation automatically catch up on boot without downloading private keys over HTTP:

```mermaid
sequenceDiagram
    participant N as Intermittent Node
    participant G as Gitea (openlab-secrets & Actions)
    N->>G: Compare /etc/openlab/last_synced_commit vs secrets HEAD SHA
    alt SHA Matches (Fast Path)
        N->>N: Write /run/openlab/synced_ok (Unlock)
    else SHA Stale (Node Missed Rotation)
        N->>G: Dispatch deploy-ssh-keys.yml (source_commit_sha, deploy_client_keys=false)
        G->>N: Auth with historical key, push latest pubkey, purge old key
        N->>N: Update last_synced_commit & write /run/openlab/synced_ok
    end
```

---

## 🚀 Key Features

* **Zero External Python Dependencies**: Runs entirely on the Python 3 standard library.
* **Day-0 Turnkey Onboarding (`lab-init`)**: Interactive TUI wizard guides initial fleet ingestion in an isolated `/tmp` workspace and generates permanent management keys.
* **Three-Phase Zero-Downtime Key Rotation**: Seamless key lifecycle management (Stage 1: Add $\rightarrow$ Stage 2: Verify $\rightarrow$ Stage 3: Remove).
* **Boot-Time Stale Key Auto-Sync (`lab-boot-sync`)**: Intermittent nodes compare `/etc/<prefix>/last_synced_commit` against `openlab-secrets` HEAD SHA and trigger a roll-forward sync using `source_commit_sha` while protected by a lockout guard (`/run/<prefix>/synced_ok`).
* **Flat LAN Architecture**: Pre-configured for standard single-subnet local area networks (`192.168.1.0/24`).
* **Multi-Distribution Linux Support**: Native support for Arch Linux, Debian, Ubuntu, Alpine, Photon OS, and generic systemd-based Linux systems.
* **Dynamic Ground-Truth Telemetry**: Machine hardware and service facts probed live via native shell scripts and compiled directly into Ansible inventories.

---

## 🛠️ Quickstart

### 1. Fast One-Line Install
```bash
curl -fsSL https://raw.githubusercontent.com/openlabops/openlabops/main/scripts/install.sh | bash
```

Or clone manually:
```bash
git clone https://github.com/openlabops/openlabops.git ~/.openlabops
cd ~/.openlabops
./bin/lab-dev-setup
```

### 2. Day-0 Cluster Onboarding
Launch the interactive onboarding wizard to configure your homelab and onboard nodes:
```bash
lab-init
```

### 3. Dynamic Fleet Operations
Manage nodes and inspect cluster health:
```bash
# Ingest a new node
lab-node add 192.168.1.50 --user admin

# Inspect fleet status and SSH key health
lab-status -k

# Launch interactive Curses operations TUI
lab-tools

# Decommission an existing node
lab-node remove node-hostname
```

---

## 📐 Invariants & Architectural Contract

* **`[INV-01]` Zero External Dependencies**: 100% Python standard library only.
* **`[INV-02]` Zero Plaintext Keys in Repository**: Private keys reside strictly on designated dev control stations in `~/.ssh/`.
* **`[INV-03]` Three-Tier Separation**:
  - `Tier 1 (core)`: `conf/core.manifest.yml` (Framework constants and specs).
  - `Tier 2 (site)`: `conf/openlab.manifest.yml` (Declarative site parameters and cluster intent).
  - `Tier 3 (node)`: Dynamic sensory facts collected into `conf/nodes/*.json` and compiled to inventory.

---

## 💬 Community & Maintenance Philosophy

* **Built with Google Antigravity (AGY) Vibe Coding**: OpenLabOps is co-authored through structured human-AI Vibe Coding using **Google Antigravity (AGY)**. By pairing a machine-enforced engineering contract (`AGENTS.md`), immutable `schema/*.cue` invariants, and a Spec-First workflow, AI agents iterate rapidly on code while staying strictly bounded. Read more in the **[AI Collaboration & SRE Methodology Wiki](https://openlabops.github.io/openlabops/methodology)**.
* **AI-Ready SRE Boundaries (`AGY-Remote`)**: The 4-repo blast-radius isolation, zero-plaintext-key design, and non-interactive CLI flags (`lab-status --json`, `lab-tools --plain`, `lab-init --with-remote-dev`) allow `AGY-Remote` agents to safely participate in daily SRE diagnostics and GitOps workflow dispatch without risking credential leakage or lockout.
* **Discussions Only**: GitHub Issues and Pull Requests are disabled. If you have questions, ideas, or feedback, join the **GitHub Discussions**.
* **Fork-Friendly**: OpenLabOps is built to be a strong foundation for private homelabs. You are warmly encouraged to **fork this repository** and customize the manifests, playbooks, and TUI to match your exact hardware and network setup.
* **AS IS**: Provided without warranties or commercial SLAs (Apache 2.0).

---

## 💖 Acknowledgments & Credits

OpenLabOps is distilled from the upstream Operations Framework, adapted and generalized for the global open-source homelab community.

