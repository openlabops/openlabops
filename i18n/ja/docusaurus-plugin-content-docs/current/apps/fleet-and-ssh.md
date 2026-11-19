---
id: fleet-and-ssh
title: フリート運用と SSH ライフサイクル
sidebar_position: 2
---

# フリート運用・SSH ライフサイクル CLI

`tools/bin/` 配下に配置され、外部 Python ライブラリ依存ゼロ（`[INV-01]`）で動作します。Ansible 実行が必要なタスクは `tools/lib/core/gitea_api.py` 経由でリモート Gitea Actions へディスパッチされます。

---

## `lab-status`

**エンジン：** `tools/lib/lab_status.py`

リアルタイムクラスター健全性ダッシュボード、SSH 鍵監視、および `authorized_keys` バックドア監査ツール。

```bash
lab-status [-q] [-k] [-a] [-n] [-d] [-p HOST] [-b | -t] [--json]
```

* `-q, --quick`：ローカルホストのみプローブ（リモートノードをスキップ）。
* `-k, --keys-only`：管理対象 SSH 秘密鍵と Agent の状態のみ表示。
* `-a, --audit-keys`：全ノードの `authorized_keys` を精査し、既知のフィンガープリントと照合して不正鍵を検出。
* `-n, --nodes-only`：サーバーノードとパッケージ状態のみ表示。
* `-p, --probe HOST`：指定ホストの詳細診断を実行（`-d` で STDERR と終了コードを表示）。
* `-b` / `-t` / `--json`：ボックスカード UI、プレーン表形式（既定）、または JSON 出力を切り替え。

---

## `lab-ssh`

**エンジン：** `tools/lib/lab_ssh.py`

SSH 鍵ライフサイクル管理および 3段階鍵ローテーションディスパッチャー。

```bash
lab-ssh [-a | --rotate-all] [--rotate-ansible] [--rotate-storage] [--rotate-git]
        [-t TARGET] [-g [HOSTNAME]] [--sync-keys] [--sync-config] [--revoke REVOKE]
```

* `--rotate-ansible` / `--rotate-git` / `--rotate-all`：Gitea Actions 経由で 3段階ゼロダウンタイム鍵ローテーションを実行。
* `-g [HOSTNAME]`：エンドポイント用 SSH 鍵ペアを生成し公開鍵を配布。
* `--sync-keys` / `--sync-config`：管理鍵および標準 `~/.ssh/config` ホストエイリアスを同期。
* `--revoke HOSTNAME`：廃止したエンドポイントの公開鍵を全ノードから失効。

---

## `lab-setup`

**エンジン：** `tools/lib/lab_setup.py`

サーバー初期構築および Setup Trigger ディスパッチャー。

```bash
lab-setup [-l | --list] [-p | --provision] [-t TARGET] [-a | --all] [-s STEP] [-m {gitea,local}]
```

* 登録済みセットアップステップ（`system_base_provisioning`、`pull_docker_compose` 等）の一覧表示や実行を Gitea Actions（`-m gitea` 既定）またはローカル Ansible（`-m local`）で実行します。

---

## `lab-upgrade`

**エンジン：** `tools/lib/lab_upgrade.py`

マルチディストリビューション Linux パッケージアップグレードダッシュボード。

```bash
lab-upgrade [-s | --serial] [-f | --force] [hosts ...]
```

* 更新保留中のノードを自動選択（またはホスト指定）し、既定では並列ダッシュボードで、`-s` 指定時は直列ストリーミングログでアップグレードを実行します。

---

## `lab-tools`

**エンジン：** `tools/lib/lab_tools.py`

状態監視、鍵ローテーション、Gitea Actions 実行ログ診断（`inspect-run <ID>`）、エンドポイント失効を統合したトップレベル Curses TUI 運用コンソール（`tools/lib/core/ui_curses.py`）。スクリプトや非 TTY 環境では `--plain` / `--no-tui` を指定します。

---

## `lab-boot-sync`

**エンジン：** `tools/lib/lab_boot_sync.py`

エンドポイント起動時公開鍵同期＆ロックアウトガード。

```bash
lab-boot-sync [-c | --check] [-f | --force] [-w | --wait] [--timeout SEC]
              [--target-host HOST] [--target-user USER]
```

* ローカル状態とリモート `openlab-secrets` の最新コミット SHA を比較し、古い場合は鍵配布ワークフローを起動して収束を待機（`-w`）後、`/run/openlab/synced_ok` を書き込んでロックアウトガードを解除します。
