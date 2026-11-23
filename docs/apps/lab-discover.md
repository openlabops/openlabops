---
id: lab-discover
title: "Sensory Discovery & Classifier"
sidebar_position: 3
---

# `lab-discover` & `classifier.py` — Sensory Discovery & Inventory Compilation

OpenLabOps strictly decouples **hardware/service telemetry** (CMDB) from **Ansible classification facts** (Inventory).

---

## `lab-discover`

**Entrypoint:** `bin/lab-discover` → **Engine:** `engine/discover.py`

`lab-discover` is a read-only sensory harvester that collects ground-truth hardware and runtime facts from managed hosts.

```bash
lab-discover [--out-dir DIR] [--node HOST] [--manifest FILE]
```

* Executes `engine/bootstrap_probe.sh` over SSH against target nodes.
* Writes structured CMDB snapshots to `node-information/node_<hostname>.json` containing:
  * CPU model/cores, total RAM, disk layout, and network interfaces/CIDRs.
  * Running Docker/container workloads and listening TCP/UDP ports.
  * Live `authorized_keys` fingerprints for security auditing.

---

## `engine/classifier.py`

Pure Python standard-library inventory compiler (`[INV-01]`, no runtime CUE dependency).

```bash
python3 engine/classifier.py [--diff | --apply] [--sync-tools]
```

* Reads classification JSONs from `conf/nodes/*.json` (or `$LAB_INIT_WORK_DIR/conf/nodes/` during `lab-init`).
* Classifies hosts across supported distributions (**Arch Linux**, **Debian**, **Ubuntu**, **Oracle Linux**, **Alpine Linux**, **VMware Photon OS**, and generic systemd Linux).
* Generates:
  * `current.json` snapshot (also mirrored to `tools/conf/current.json` or `/usr/local/bin/openlab/conf/current.json`).
  * Pre-classified `ansible/inventory/hosts.yml` (grouped by OS family, role, and subnet).
* When `LAB_INIT_WORK_DIR` is active, all outputs stay inside `/tmp` so the incubator repository remains clean.
