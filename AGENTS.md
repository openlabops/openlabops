# OpenLabOps Engineering Contract & Invariant Manifest
<!-- MACHINE-OPTIMIZED SPECIFICATION: STRICT COMPLIANCE REQUIRED FOR ALL AI AGENTS -->

> **System Notice for AI Coding Assistants**:
> This repository is the **OpenLabOps Operations Hub (`openlabops`)**.
> All homelab IaC playbooks, zero-dependency CLI tools, CI/CD workflows, and declarative manifests converge here.
> Every AI agent operating on this codebase **MUST strictly follow the Hard Architectural Invariants** below.

---

## 1. HARD ARCHITECTURAL INVARIANTS (NON-NEGOTIABLE)

| Constraint ID | Rule Description | Strict Compliance Requirement |
| :--- | :--- | :--- |
| **[INV-01]** | **Zero External Dependencies** | **MUST NOT** import third-party Python packages (`NO pip`, `NO requests`, `NO pyyaml`). Use **100% Python 3 standard library** only (`urllib.request`, `json`, `subprocess`, `sys`, `pathlib`, `os`, `shutil`). |
| **[INV-02]** | **Zero Credentials in Repository** | **STRICTLY FORBIDDEN** to store plain SSH private keys (`*.key`) or API tokens in this repository. All console tools and Ansible playbooks **MUST directly leverage the Console host's OpenSSH environment** (`~/.ssh/`). |
| **[INV-03]** | **Three-Tier Separation & Template Compiler Architecture** | • `Tier 1 (core)`: `conf/core.manifest.yml`: Framework Specification.<br>• `Tier 2 (site)`: `conf/openlab.manifest.yml`: Site-Specific Intent populated by `lab-init`.<br>• `Tier 3 (node)`: Machine Telemetry Facts collected into `conf/nodes/*.json` and compiled to inventory.<br>• **Zero Static Config in Master**: Concrete inventory files are dynamically compiled. |
| **[INV-04]** | **Sensory Ground Truth & Pure JSON Telemetry** | Dynamic node telemetry is probed live and stored as pure JSON (`conf/nodes/*.json`). |
| **[INV-05]** | **Flat LAN Network Scope** | Pre-configured for Flat LAN (`192.168.1.0/24`). No proprietary mesh or gateway appliances required. |
| **[INV-06]** | **Centralized Documentation Hub** | All Markdown documentation resides in `docs/`. |
| **[INV-07]** | **Canonical Key Roles** | Canonical neutral roles (`ansible`, `user`, `git`) mapped to site keys (`ansible.key`, `id_user.key`, `git.key`). |
| **[INV-08]** | **Non-Destructive Safe Evolution** | Preserves user configurations and maintains backward compatibility. |
| **[INV-09]** | **Production-Tool Verification** | Integration tests drive official production tools directly (`bin/lab-init`, `bin/lab-node`). |
| **[INV-10]** | **Spec-First Pipeline** | Align documentation first, update schemas, then write code. |
| **[INV-11]** | **Zero Repo Pollution** | All intermediate artifacts from tests and builds reside in `/tmp/` and are purged on exit. |
| **[INV-12]** | **Zero-Leakage Sanitization Gate** | Distilled repository and generated manifests must contain zero private infrastructure identifiers, credentials, or duplicate placeholder CIDRs. |

---

## 2. REPOSITORY TOPOLOGY

```text
openlabops/
├── bin/                        # Entry CLI scripts (lab-init, lab-node, lab-test, lab-apply, lab-diff)
├── engine/                     # Core execution engines (classifier, compiler, discover, initialize, onboard)
├── schema/                     # CUE schema specifications (invariants, network, roles, keys, nodes)
├── conf/                       # Centralized configuration SSOT (core.manifest.yml, openlab.manifest.yml)
├── ansible/                    # Stateless Ansible playbooks and generic roles
├── tools/                      # Zero-dependency Python CLI tools and libraries (tools/bin/lab-*, tools/lib/)
├── lang/                       # i18n dictionaries (en_US.json, zh_TW.json, ja_JP.json)
├── workflows/                  # CI/CD action templates
├── templates/                  # Output templates
└── tests/                      # Verification test suites and mock sandbox
```

