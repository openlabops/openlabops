---
id: lab-fleet-ops
title: "セットアップ・アップグレード・管理コンソール"
sidebar_position: 6
---

# セットアップ・アップグレード・設定・バックアップ CLI

* **`lab-setup`**：プロビジョニングステップの一覧・実行（`-l`, `-p`, `-t`, `-a`, `-s`, `-m {gitea,local}`）。
* **`lab-upgrade`**：マルチディストリビューション一括パッケージ更新（`-s`, `-f`）。
* **`lab-tools`**：Curses TUI 管理コンソール（`inspect-run <ID>`, `--plain`/`--no-tui`）。
* **`lab-backup`**：ゲートウェイ設定バックアップおよび共通設定ブロードキャスト（`-a`, `-g`, `-b`, `-s`）。
* **`lab-config`**：双方向 GitOps 設定管理（`--init`, `--show`, `--diff`, `--update`, `--reset`, `--restore`）。
* **`lab-info`**：CMDB ハードウェア・パッケージ監査と Markdown マニュアル生成（`-a`, `-d`, `-p`, `-r`）。
