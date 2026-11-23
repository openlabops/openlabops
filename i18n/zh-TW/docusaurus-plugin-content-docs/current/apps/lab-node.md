---
id: lab-node
title: "節點納管 (lab-node)"
sidebar_position: 2
---

# `lab-node` — 動態節點納管與清冊管理

**入口點：** `bin/lab-node` → `tools/bin/lab-node` → **引擎：** `tools/lib/lab_node.py` 與 `engine/onboard.py`

`lab-node` 負責節點的新增、移除、列舉與清冊同步，透過 PTY 模擬真人終端完成 SSH 認證，並擷取乾淨的 OS 分類事實。

## 語法

```bash
lab-node {add,remove,list,sync} [OPTIONS]
```

## 子指令

* **`add <IP/Host> [--user USER] [--port PORT] [--key FILE]`**：以 `execute_pty_ssh()` 連線並串流執行 `bootstrap_probe.sh`，寫入 `conf/nodes/<hostname>.json` 後重編 `hosts.yml`。
* **`remove <hostname>`**：封存並移除節點分類檔，重新編譯清冊快照。
* **`list`**：列出所有已納管節點、IP 與角色。
* **`sync`**：重新執行 `classifier.py --apply` 同步 `current.json` 與 `hosts.yml`。

## 金鑰優先順序與 PTY 執行（`engine/onboard.py`）

1. **Day-0 vs. Day-2 金鑰優先順序**：
   * **Day-0（有傳入 `ephemeral_pubkey`）**：即使管理機已存在 `~/.ssh/<target_user>.key`，仍一律優先使用臨時引導金鑰開門，再由 `lab-init` Step 5 輪替為正式金鑰。
   * **Day-2（`ephemeral_pubkey is None`）**：採用管理機既有的 `~/.ssh/<target_user>.key`，並以 `ssh-keygen -y -P "" -f` 反推真實公鑰。
2. **PTY 擬人互動（`execute_pty_ssh`）**：使用內建 `pty` 處理密碼、`sudo` 與 host key 提示。
3. **儲存路徑解析（`_get_nodes_dir()`）**：`lab-init` 期間寫入 `/tmp/.../conf/nodes/`；Day-2 單機執行時寫入 `conf/nodes/<hostname>.json`。
