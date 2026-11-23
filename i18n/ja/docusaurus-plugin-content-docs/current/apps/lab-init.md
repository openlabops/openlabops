---
id: lab-init
title: "Day-0 初期化 (lab-init)"
sidebar_position: 1
---

# `lab-init` — Day-0 初期化コマンダー

**エントリポイント:** `bin/lab-init` → **エンジン:** `engine/initialize.py`

```bash
lab-init [--lang {zh_TW,en_US,ja_JP}] [--manifest FILE] [--legacy-key FILE]
         [--non-interactive] [--with-gitea-runner] [--with-remote-dev]
         [--skip-nodes HOSTS] [--include-appliances] [--include-endpoints]
```

* `/tmp/lab_init_work_*`（`LAB_INIT_WORK_DIR`）に中間生成物を隔離し、リポジトリを汚さずに 4リポジトリ連携・一時鍵ブートストラップ・`ssh-keygen -y` 導出修復・`_run_ssh_with_backoff` による3段階鍵ローテーションを実行します。
