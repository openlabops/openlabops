---
id: three-tier-ssot
title: "3層 SSOT と 4リポジトリ連携"
sidebar_position: 1
---

# 3層 SSOT と 4リポジトリ GitOps 連携

OpenLabOps は不変のフレームワーク契約、サイト宣言パラメータ、動的なマシン事実を 3層に分離し、4つの下流 Gitea リポジトリで権限を隔離します。

## 3層分離モデル

| 層 | スコープ | 配置場所 | 可変性 |
| :--- | :--- | :--- | :--- |
| **Tier 1 (`core`)** | 不変フレームワーク契約、不変条件 (`[INV-01]`–`[INV-09]`)、標準鍵ロール | `conf/core.manifest.yml`, `schema/*.cue` | サイト横断で不変 |
| **Tier 2 (`site`)** | クラスター名、ドメイン、Flat LAN サブネット、ゲートウェイ、Gitea エンドポイント | `conf/openlab.manifest.yml` (`lab-init` 中は `/tmp/lab_init_work_*`) | サイト固有 |
| **Tier 3 (`node`)** | OS 分類事実 (`conf/nodes/*.json`) と CMDB テレメトリ (`node-information/node_*.json`) | `openlab-configs` | ホストごとに動的 |

## ブラストラディウス・トークン隔離

`lab-init` は CI ボットに Ansible Playbook の書き込み権限を与えず、4つのリポジトリへ権限を分割します：

1. **`<prefix>-operations`**: Playbook、Role、エンジン、CLI ツール（`ci-bot` は**読み取り専用**）。
2. **`<prefix>-workflows`**: Gitea Actions ワークフロー（**読み取り / ディスパッチ**）。
3. **`<prefix>-configs`**: CMDB `node-information/node_*.json`、パッケージ一覧（**テレメトリ書き込み**）。
4. **`<prefix>-secrets`**: 公開鍵、エンドポイント鍵台帳、暗号化シークレット（**鍵ポリシー読み取り**）。
