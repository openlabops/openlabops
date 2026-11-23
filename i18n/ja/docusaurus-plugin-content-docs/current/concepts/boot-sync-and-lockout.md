---
id: boot-sync-and-lockout
title: "期限切れ鍵の起動時自動同期とロックアウト保護"
sidebar_position: 4
---

# 期限切れ鍵の起動時自動同期とロックアウト保護

ワークステーションやノート PC などの間欠稼働ノード（`always_online: false`）は、電源オフ中に鍵ローテーションを逃すことがあります。OpenLabOps は HTTP 経由で秘密鍵を配布することなく（`[INV-02]`）、起動時に自動追従します：

```mermaid
sequenceDiagram
    participant N as 間欠稼働ノード
    participant G as Gitea (openlab-secrets & Actions)
    N->>G: /etc/<prefix>/last_synced_commit と secrets HEAD SHA を比較
    alt SHA 一致 (Fast Path)
        N->>N: /run/<prefix>/synced_ok を作成 (ロック解除)
    else SHA 相違 (ローテーション未適用)
        N->>G: deploy-ssh-keys.yml を起動 (source_commit_sha, deploy_client_keys=false)
        G->>N: source_commit_sha の旧鍵で接続し、最新公開鍵を配布・旧鍵削除
        N->>N: last_synced_commit 更新後 /run/<prefix>/synced_ok を作成
    end
```

* **Secrets Git SHA インデックス (`tools/lib/lab_boot_sync.py`)**: `/etc/<prefix>/last_synced_commit` と `<prefix>-secrets` の `HEAD` を比較します。
* **ロックアウトガード (`tools/lib/core/lockout.py`)**: `/run/<prefix>/synced_ok` が作成されるまで、間欠ノード上の `lab-*` 自動化操作をロックします。
