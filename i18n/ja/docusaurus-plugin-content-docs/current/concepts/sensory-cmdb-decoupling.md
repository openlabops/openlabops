---
id: sensory-cmdb-decoupling
title: "センサーハードウェア探索と分類の分離"
sidebar_position: 5
---

# センサーハードウェア探索とインベントリ分類の分離

OpenLabOps は **Ansible 用の分類情報** と **CMDB ハードウェアテレメトリ** を厳格に分離しています。

| 項目 | インベントリ分類 (`lab-node` / `classifier.py`) | センサー CMDB (`lab-discover` / `bootstrap_probe.sh`) |
| :--- | :--- | :--- |
| **出力先** | `conf/nodes/<hostname>.json` / `ansible/inventory/hosts.yml` | `node-information/node_<hostname>.json` (`<prefix>-configs`) |
| **内容** | `hostname`, `primary_ip`, `os_family`, `distribution`, `node_category` | CPU, RAM, ディスク, 待機ポート, コンテナ, `authorized_keys` フィンガープリント |

`engine/classifier.py` は Python 標準ライブラリのみで **Arch Linux**、**Debian**、**Ubuntu**、**Oracle Linux**、**Alpine Linux**、**VMware Photon OS** 等を自動分類し `hosts.yml` を生成します。
