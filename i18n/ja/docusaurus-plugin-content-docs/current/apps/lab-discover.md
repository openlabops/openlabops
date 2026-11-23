---
id: lab-discover
title: "センサー探索と分類エンジン"
sidebar_position: 3
---

# `lab-discover` & `classifier.py`

* **`lab-discover`**（`engine/discover.py`）：`engine/bootstrap_probe.sh` を SSH 経由で実行し、ハードウェア・サービス・`authorized_keys` 指紋を `node-information/node_<hostname>.json` に収集します。
* **`engine/classifier.py`**：`conf/nodes/*.json`（`lab-init` 中は `/tmp`）から `current.json` と `ansible/inventory/hosts.yml` を生成します。
