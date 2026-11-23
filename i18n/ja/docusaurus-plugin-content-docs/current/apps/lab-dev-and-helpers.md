---
id: lab-dev-and-helpers
title: "開発環境・テスト・補助スクリプト"
sidebar_position: 7
---

# 開発環境・テスト・補助スクリプト

* **`lab-dev-setup`**（`bin/lab-dev-setup`）：`ansible`、`cue`、`docker` のセットアップ（`--check`, `--force`）。
* **`lab-test`**（`bin/lab-test`）：サンドボックス＆受け入れテスト（`-m`, `-a`, `-g`, `--dr`, `--kvm`）。
* **`lab-man`**（`tools/bin/lab-man`）：組み込み CLI マニュアルビューア（`lab-man status` 等）。

| スクリプト (`tools/bin/`) | 用途 |
| :--- | :--- |
| **`sync-ops-tools`** | 対象ノードへの CLI ツール配信・更新 |
| **`sync-ssh-config`** | `~/.ssh/config` ホストエイリアスの同期 |
| **`sync-ssh-keys`** | Gitea Runner 経由での管理鍵配布 |
| **`generate-host-ssh-key`** | エンドポイント専用 Ed25519 鍵生成と公開鍵配布 |
| **`revoke-host-ssh-key`** | 廃止エンドポイントの公開鍵を全ノードから失効 |
| **`render-node-doc`** | `node_*.json` から Markdown ノードマニュアルを生成 |
