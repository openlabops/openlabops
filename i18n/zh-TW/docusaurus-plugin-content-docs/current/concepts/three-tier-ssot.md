---
id: three-tier-ssot
title: "三層分離 SSOT 與四庫聯邦"
sidebar_position: 1
---

# 三層分離 SSOT 與四庫 GitOps 聯邦

OpenLabOps 將不可變框架合約、站點宣告參數與動態機器事實拆分為三個層級，並透過四個下游 Gitea 倉庫進行權限隔離。

## 三層分離模型

| 層級 | 範圍 | 位置 | 可變性 |
| :--- | :--- | :--- | :--- |
| **Tier 1 (`core`)** | 不可變框架合約、架構不變量（`[INV-01]`–`[INV-09]`）、標準金鑰角色 | `conf/core.manifest.yml`, `schema/*.cue` | 跨站點不可變 |
| **Tier 2 (`site`)** | 叢集名稱、網域、Flat LAN 網段、閘道、Gitea 端點、管理/Ansible 帳號 | `conf/openlab.manifest.yml`（`lab-init` 期間寫入 `/tmp/lab_init_work_*`） | 依站點而異 |
| **Tier 3 (`node`)** | OS 分類事實（`conf/nodes/*.json`）與 CMDB 遙測（`node-information/node_*.json`） | `openlab-configs` | 依主機動態變化 |

## 爆炸半徑（Blast-Radius）Token 隔離

`lab-init` 不會讓 CI 機器人擁有修改 Ansible Playbook 的權限，而是將下游狀態拆分為四個權限嚴格隔離的倉庫：

1. **`<prefix>-operations`**：Playbook、Role、引擎與 CLI 工具（`ci-bot` **唯讀**）。
2. **`<prefix>-workflows`**：Gitea Actions 工作流與複合 Action（**讀取 / 觸發**）。
3. **`<prefix>-configs`**：CMDB `node-information/node_*.json`、套件清單、節點手冊（**寫入遙測**）。
4. **`<prefix>-secrets`**：公鑰、端點金鑰登錄檔與加密密文（**讀取金鑰策略**）。

即使 `ci-bot` Token 外洩，攻擊者也無法竄改 `<prefix>-operations` 內的 Ansible Playbook。
