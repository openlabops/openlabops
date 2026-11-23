---
id: zero-dep-runner-model
title: "零依賴標準庫與 Act Runner 模型"
sidebar_position: 6
---

# 零外部依賴標準庫與 Gitea Act Runner 模型

## `[INV-01]` 零外部 Python 依賴

所有控制平面引擎（`engine/*.py`）與端點工具（`tools/lib/*.py`）100% 使用 Python 3 標準庫撰寫（無 `pip`、`requests`、`pyyaml`、`paramiko`）：

* **YAML 解析**：`tools/lib/core/yaml_parser.py`
* **Gitea REST API**：`tools/lib/core/gitea_api.py`（基於 `urllib.request`）
* **終端 TUI**：`tools/lib/core/ui_curses.py` 與 `engine/bsd_dialog.py`（基於 `curses`）
* **PTY SSH 自動化**：`engine/onboard.py`（基於 `pty`、`os`、`select`）

確保任何最小化安裝的 Linux 主機皆可開箱即用，不會發生 virtualenv 或套件版本漂移。

## 集中式 Gitea Act Runner 執行模型

受控端點與維運工作站**不需要**本機安裝 `ansible-core`：

1. 維運者執行 `lab-ssh`、`lab-setup`、`lab-upgrade` 或 `lab-backup`。
2. CLI 透過 Gitea API 向 `<prefix>-workflows` 派發 `workflow_dispatch` 事件。
3. **Gitea Act Runner** 容器（預裝 `ansible-core`）唯讀簽出 `<prefix>-operations`、`<prefix>-configs` 與 `<prefix>-secrets`，並透過 SSH 對目標節點執行無狀態 Ansible Playbook。
