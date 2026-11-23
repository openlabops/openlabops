---
id: intro
slug: /
title: OpenLabOps Wiki
sidebar_position: 1
---

# OpenLabOps: Zero-Dependency Declarative Homelab Operations Framework

**OpenLabOps** is an open-source, turnkey operations control hub and GitOps management framework for modern homelabs and private Linux fleets. Built with **100% Python 3 standard library** and stateless Ansible playbooks, it delivers Day-0 cluster onboarding, three-phase zero-downtime SSH key rotation, live sensory hardware discovery, and declarative GitOps synchronization without external Python dependencies (`NO pip`, `NO requests`, `NO pyyaml`).

## Quickstart

```bash
# 1. One-line install on your control workstation
curl -fsSL https://raw.githubusercontent.com/openlabops/openlabops/main/scripts/install.sh | bash

# 2. Launch Day-0 interactive onboarding wizard
lab-init

# 3. Manage nodes dynamically
lab-node add 192.168.1.50 --user admin
lab-status -k
lab-tools
```

## Core Architectural Invariants

| ID | Principle | Enforcement |
| :--- | :--- | :--- |
| **INV-01** | **Zero External Dependencies** | 100% Python 3 standard library (`urllib.request`, `json`, `subprocess`, `pathlib`, `curses`) with built-in YAML parsing. |
| **INV-02** | **Zero Plaintext Keys in Repo** | Private keys never enter Git repositories; all tools leverage the control workstation's native `~/.ssh/` and `ssh-agent`. |
| **INV-03** | **Three-Tier Separation** | Strict separation between immutable `core` specs, declarative `site` intent, and dynamic `node` telemetry. |
| **INV-04** | **Sensory Ground Truth** | Immutable invariants live in `schema/*.cue`; live machine facts are probed at runtime into pure JSON (`conf/nodes/*.json`). |

## Wiki Navigation

* **[System Architecture](./architecture)** — Three-tier separation, 4-repository federation, Flat LAN networking, and CUE constraints.
* **[Security Policy & Key Lifecycle](./security)** — Canonical key roles, 3-phase zero-downtime rotation, IP-restricted `authorized_keys`, and `lab-boot-sync` lockout guard.
* **[Testing Methodology & Sandbox](./testing)** — Production-tool verification, Dagger DinD, multi-distro Docker sandbox, PTY simulator, and SHA-256 DR drills.
* **[Antigravity Vibe Coding & AI SRE](./methodology)** — Spec-First human-AI collaboration workflow and how `AGY-Remote` safely participates in SRE within hard architectural boundaries.
* **[CLI Applications & Internals](./apps/onboarding-and-compiler)** — Detailed usage, flags, and internal mechanics for every `lab-*` command and helper script.
