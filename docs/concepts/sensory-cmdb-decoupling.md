---
id: sensory-cmdb-decoupling
title: "Sensory Discovery vs. Classification"
sidebar_position: 5
---

# Sensory Hardware Discovery vs. Inventory Classification

OpenLabOps enforces a strict boundary between **what a machine is for Ansible** and **what hardware/services are currently running on it**.

## Two Separate Pipelines

| Aspect | Inventory Classification (`lab-node` / `classifier.py`) | Sensory CMDB (`lab-discover` / `bootstrap_probe.sh`) |
| :--- | :--- | :--- |
| **Output Path** | `conf/nodes/<hostname>.json` & `ansible/inventory/hosts.yml` | `node-information/node_<hostname>.json` (in `<prefix>-configs`) |
| **Contents** | `hostname`, `primary_ip`, `os_family`, `distribution`, `node_category`, `capabilities` | CPU, RAM, disks, network interfaces, listening ports, Docker containers, `authorized_keys` fingerprints |
| **Hardware Telemetry?** | **Never** (keeps inventory diffs clean and deterministic) | **Yes** (audited snapshot for CMDB & security) |

## Multi-Distro Classification (`engine/classifier.py`)

`classifier.py` reads `conf/nodes/*.json` using pure Python stdlib (zero runtime CUE dependency) and compiles `ansible/inventory/hosts.yml` grouped by:
* **OS Family / Distro**: Arch Linux, Debian, Ubuntu, Oracle Linux, Alpine Linux, VMware Photon OS, generic systemd Linux.
* **Node Role**: `servers`, `dev`, `desktop`, `storage`, `hypervisor`.
* **Subnet**: Flat LAN (`192.168.1.0/24`) or custom site subnets.
