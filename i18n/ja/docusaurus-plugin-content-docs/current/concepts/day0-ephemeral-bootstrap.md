---
id: day0-ephemeral-bootstrap
title: "Day-0 一時ブートストラップと /tmp 隔離"
sidebar_position: 2
---

# Day-0 一時ブートストラップと `/tmp` ワークスペース隔離

## `/tmp` 隔離の理由

インキュベーターリポジトリ上で直接 `lab-init` を実行すると、追跡中のテンプレート（`conf/openlab.manifest.yml`、`ansible/group_vars/all.yml`、`tools/conf/tools.config.json`）が上書きされ、ノード JSON が残留してしまいます。

1. **`LAB_INIT_WORK_DIR` (`/tmp/lab_init_work_*`)**:
   `engine/initialize.py` は起動時に `/tmp` に一時ワークスペースを作成し、終了時に `atexit` で自動削除します。`onboard.py` と `classifier.py` は `LAB_INIT_WORK_DIR` を検出すると `/tmp` 配下にのみ出力します。
2. **一時ブートストラップ鍵 (`/tmp/lab_bootstrap_keys/`)**:
   `from="..."` 制限なしの一時 Ed25519 鍵ペアを `/tmp` に生成します（`[INV-02]`）。Day-0 では `~/.ssh/<target_user>.key` が存在していても `ephemeral_pubkey` を優先使用します。
3. **PTY 人間シミュレーション (`execute_pty_ssh`)**:
   Python 標準ライブラリの `pty` のみで SSH / `sudo` パスワードプロンプトを処理します。
4. **レート制限バックオフ (`_run_ssh_with_backoff`)**:
   `kex_exchange_identification` や `Connection reset by peer` などの一時的な SSH ハンドシェイクエラーを指数バックオフで自動リトライします。
