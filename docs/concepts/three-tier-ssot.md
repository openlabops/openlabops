---
id: three-tier-ssot
title: "Three-Tier SSOT & 4-Repo Federation"
sidebar_position: 1
---

# Three-Tier SSOT & Four-Repository GitOps Federation

OpenLabOps separates immutable framework contracts, declarative site parameters, and dynamic machine facts across three tiers and four downstream Gitea repositories.

## Three-Tier Separation Model

| Tier | Scope | Location | Mutability |
| :--- | :--- | :--- | :--- |
| **Tier 1 (`core`)** | Immutable framework contracts, invariants (`[INV-01]`–`[INV-09]`), canonical key roles | `conf/core.manifest.yml`, `schema/*.cue` | Immutable across sites |
| **Tier 2 (`site`)** | Cluster name, domain, Flat LAN subnet, gateway, Gitea endpoint, admin/ansible users | `conf/openlab.manifest.yml` (or `/tmp/lab_init_work_*` during `lab-init`) | Site-specific |
| **Tier 3 (`node`)** | OS classification facts (`conf/nodes/*.json`) & CMDB telemetry (`node-information/node_*.json`) | `openlab-configs` | Dynamic per host |

## Blast-Radius Token Isolation

Instead of giving a CI bot write access to Ansible playbooks, `lab-init` provisions four repositories with strict `ci-bot` permission boundaries:

1. **`<prefix>-operations`**: Playbooks, roles, engine, and CLI tools (**Read-Only** for `ci-bot`).
2. **`<prefix>-workflows`**: Gitea Actions workflows & composite actions (**Read / Dispatch**).
3. **`<prefix>-configs`**: CMDB `node-information/node_*.json`, package lists, rendered node docs (**Write Telemetry**).
4. **`<prefix>-secrets`**: Public keys, endpoint registries, encrypted secrets (**Read Key Policies**).

Because `ci-bot` cannot modify `<prefix>-operations`, a compromised CI token cannot inject malicious tasks into Ansible playbooks.
