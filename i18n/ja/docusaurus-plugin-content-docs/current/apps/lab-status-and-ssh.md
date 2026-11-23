---
id: lab-status-and-ssh
title: "クラスター健全性と SSH ライフサイクル"
sidebar_position: 5
---

# クラスター健全性と SSH ライフサイクル CLI

* **`lab-status`**（`tools/lib/lab_status.py`）：クラスター健全性チェックおよび `authorized_keys` 監査（`-q`, `-k`, `-a`, `-n`, `-d`, `-p HOST`, `-b`/`-t`/`--json`）。
* **`lab-ssh`**（`tools/lib/lab_ssh.py`）：3段階ゼロダウンタイム鍵ローテーション、`~/.ssh/config` 同期、エンドポイント鍵発行・失効。
* **`lab-boot-sync`**（`tools/lib/lab_boot_sync.py`）：`/etc/<prefix>/last_synced_commit` と `<prefix>-secrets` HEAD SHA を比較し、未同期時は `deploy-ssh-keys.yml` でロールフォワード同期後 `/run/<prefix>/synced_ok` を作成してロック解除します。
