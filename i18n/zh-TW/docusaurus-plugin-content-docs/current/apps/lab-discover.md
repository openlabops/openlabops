---
id: lab-discover
title: "感官探測與分類引擎"
sidebar_position: 3
---

# `lab-discover` 與 `classifier.py`

OpenLabOps 嚴格分離硬體/服務遙測（CMDB）與 Ansible 清冊分類事實。

## `lab-discover`

**入口點：** `bin/lab-discover` → **引擎：** `engine/discover.py`

```bash
lab-discover [--out-dir DIR] [--node HOST] [--manifest FILE]
```

透過 SSH 執行 `engine/bootstrap_probe.sh`，將 CPU、RAM、磁碟、網段、Docker 容器、監聽埠與 `authorized_keys` 指紋寫入 `node-information/node_<hostname>.json`。

## `engine/classifier.py`

```bash
python3 engine/classifier.py [--diff | --apply] [--sync-tools]
```

以純 Python 標準庫讀取 `conf/nodes/*.json`（`lab-init` 期間為 `$LAB_INIT_WORK_DIR/conf/nodes/`），分類支援 **Arch Linux**、**Debian**、**Ubuntu**、**Oracle Linux**、**Alpine Linux**、**VMware Photon OS** 與一般 systemd Linux，並產生 `current.json` 與 `ansible/inventory/hosts.yml`。
