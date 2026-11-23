---
id: lab-dev-and-helpers
title: "開發環境、測試與輔助腳本"
sidebar_position: 7
---

# 開發環境、測試與輔助腳本

* **`lab-dev-setup`**（`bin/lab-dev-setup`）：透過 `dev-environment.yml` 確保 `ansible`、`cue`、`docker` 就緒（`--check`, `--force`）。
* **`lab-test`**（`bin/lab-test`）：沙箱與驗收測試總控（`-m` 手動、`-a` 全自動 E2E、`-g` Dagger DinD、`--dr` 災難復原演練、`--kvm`）。
* **`lab-man`**（`tools/bin/lab-man`）：內建終端指令手冊檢視器（如 `lab-man status`、`lab-man init`）。

## `tools/bin/` 獨立輔助腳本

| 腳本 | 引擎 | 用途 |
| :--- | :--- | :--- |
| **`sync-ops-tools`** | `tools/lib/sync_ops_tools.py` | 檢查版本並部署/更新目標節點的 `openlabops` CLI 工具。 |
| **`sync-ssh-config`** | `tools/lib/sync_ssh_config.py` | 渲染並同步標準 `~/.ssh/config` 主機別名。 |
| **`sync-ssh-keys`** | `tools/lib/sync_ssh_keys.py` | 透過 Gitea Runner 部署並修復受管 SSH 金鑰權限。 |
| **`generate-host-ssh-key`** | `tools/lib/generate_host_ssh_key.py` | 生成端點專用 Ed25519 金鑰對並派發公鑰部署。 |
| **`revoke-host-ssh-key`** | `tools/lib/revoke_host_ssh_key.py` | 撤銷除役端點於全網的公鑰授權。 |
| **`render-node-doc`** | `tools/lib/render_node_doc.py` | 將 `node_*.json` CMDB 遙測渲染為 Markdown 節點手冊。 |
