---
id: lab-node
title: "ノードオンボーディング (lab-node)"
sidebar_position: 2
---

# `lab-node` — 動的ノード登録とインベントリ管理

**エントリポイント:** `bin/lab-node` → `tools/bin/lab-node` → **エンジン:** `tools/lib/lab_node.py` / `engine/onboard.py`

```bash
lab-node {add,remove,list,sync} [OPTIONS]
```

* Day-0（`ephemeral_pubkey` 指定時）は既存 `~/.ssh/<target_user>.key` があっても一時鍵を優先し、Day-2 単体登録時は `ssh-keygen -y -P "" -f` で公開鍵を導出します。
* `LAB_INIT_WORK_DIR` 設定時は `/tmp/.../conf/nodes/` に、通常時は `conf/nodes/<hostname>.json` に保存します。
