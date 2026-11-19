---
id: ops-and-helpers
title: 設定同期・バックアップ・補助ツール
sidebar_position: 3
---

# 設定同期・バックアップ・補助ツール CLI

---

## `lab-backup`

**エンジン：** `tools/lib/lab_backup.py`

クラスターバックアップおよび共有設定ブロードキャストスイート。

```bash
lab-backup [-a | --all] [-g | --gateway] [-b | --broadcast] [-s SOURCE]
```

* `-g, --gateway`：ゲートウェイのファイアウォールおよび DNS 設定をバックアップ。
* `-b, --broadcast`：`-s SOURCE` から共有ローカル設定を収集しフリート全体へ配信。
* `-a, --all`：ゲートウェイバックアップと共有設定配信の両方を実行。

---

## `lab-config`

**エンジン：** `tools/lib/lab_config.py`

双方向 GitOps ローカル設定コントローラー（`/usr/local/etc` / `backup.yml`）。

```bash
lab-config [--init | --show | --diff | --update | --reset | --restore] [-m MESSAGE]
```

* `--init`：リモートテンプレートからローカル設定を初期化。
* `--show` / `--diff`：ローカル設定の表示またはリモート HEAD との差分比較。
* `--update`：ローカル変更を検証・プッシュしてクラスター同期をトリガー。
* `--reset` / `--restore`：変更を破棄してリモート HEAD へ戻すか、`HEAD~1` へロールバック。

---

## `lab-info`

**エンジン：** `tools/lib/lab_info.py`

CMDB ハードウェア・パッケージテレメトリスイート。

```bash
lab-info [-a | --all] [-d | --dispatch-only] [-p | --pull-only] [-r | --render-only]
```

* Gitea Actions 監査ワークフローを起動（`-d`）、更新された `openlab-configs` をプル（`-p`）、`node-information/node_*.json` から Markdown ノードマニュアルを生成（`-r`）します。

---

## `lab-man`

**スクリプト：** `tools/bin/lab-man`（`bin/lab-man` シンボリックリンク）

組み込みターミナルマニュアルビューアー（例：`lab-man status`、`lab-man init`）。

---

## スタンドアロン補助スクリプト (`tools/bin/`)

| スクリプト | エンジン | 用途 |
| :--- | :--- | :--- |
| **`sync-ops-tools`** | `tools/lib/sync_ops_tools.py` | バージョン確認と管理対象ノードへの `openlabops` CLI ツール配布・更新（`-c`、`-f`、`-l`）。 |
| **`sync-ssh-config`** | `tools/lib/sync_ssh_config.py` | 標準 `~/.ssh/config` ホストエイリアスの生成・同期（`-p openlab \| endpoint`）。 |
| **`sync-ssh-keys`** | `tools/lib/sync_ssh_keys.py` | Gitea Runner 経由での管理 SSH 鍵配布とパーミッション修正（`-n`、`-u`、`-k`）。 |
| **`generate-host-ssh-key`** | `tools/lib/generate_host_ssh_key.py` | エンドポイント端末専用の Ed25519 鍵ペア生成（`-H HOSTNAME`）と公開鍵デプロイ。 |
| **`revoke-host-ssh-key`** | `tools/lib/revoke_host_ssh_key.py` | 指定エンドポイントの公開鍵を全ノードから失効（`-H HOSTNAME`、`--keep-secrets`、`-l`、`-y`）。 |
| **`render-node-doc`** | `tools/lib/render_node_doc.py` | `node_*.json` CMDB ファイルを人間が読める Markdown マニュアルへ変換（`-o` / `-d`）。 |
