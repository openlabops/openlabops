---
id: three-phase-key-rotation
title: "3段階ゼロダウンタイム鍵ローテーション"
sidebar_position: 3
---

# 3段階ゼロダウンタイム SSH 鍵ローテーション

OpenLabOps は稼働中の SSH 鍵を単一ステップで上書きしません。Day-0 引き継ぎ（`lab-init`）および Day-2 ローテーション（`lab-ssh --rotate-*`）のいずれも 3段階プロトコルに従います：

```mermaid
sequenceDiagram
    participant C as 制御端末 / Runner
    participant N as 管理対象ノード
    Note over C,N: Stage 1 - 2鍵共存
    C->>N: from="<subnets>" 制限付きで新公開鍵を追記
    Note over C,N: Stage 2 - 接続検証
    C->>N: 新秘密鍵で BatchMode=yes SSH 接続を検証
    Note over C,N: Stage 3 - 旧鍵削除
    C->>N: authorized_keys から旧/一時公開鍵を削除
```

* **`ssh-keygen -y` による公開鍵導出**: 秘密鍵から `ssh-keygen -y -P "" -f` で公開鍵を直接導出し、不整合な `*.key.pub` を自動修復します。
* **`from="..."` サブネット制限 (`[INV-05]`)**: 許可された内部サブネットからのみログインを許可します。
