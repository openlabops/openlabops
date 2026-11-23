---
id: intro
slug: /
title: OpenLabOps Wiki
sidebar_position: 1
---

# OpenLabOps：零依賴宣告式 Homelab 維運框架

**OpenLabOps** 是一套專為現代 Homelab 與私有 Linux 集群打造的開源 GitOps 維運控制框架。全系統採用 **100% Python 3 標準函式庫**與無狀態 Ansible 劇本建構，免除任何第三方 Python 套件依賴（`NO pip`、`NO requests`、`NO pyyaml`），開箱即具備 Day-0 互動式納管、三階段零停機 SSH 金鑰輪替、即時硬體探測與 GitOps 雙向同步能力。

## 快速開始 (Quickstart)

```bash
# 1. 於控制端工作站單行安裝
curl -fsSL https://raw.githubusercontent.com/openlabops/openlabops/main/scripts/install.sh | bash

# 2. 啟動 Day-0 互動式初始化精靈
lab-init

# 3. 動態管理節點與集群健康度
lab-node add 192.168.1.50 --user admin
lab-status -k
lab-tools
```

## 核心架構不變量

| 編號 | 原則 | 強制規範 |
| :--- | :--- | :--- |
| **INV-01** | **零外部依賴** | 100% 使用 Python 3 標準函式庫（`urllib.request`, `json`, `subprocess`, `pathlib`, `curses`），內建 YAML 解析器。 |
| **INV-02** | **倉庫零明文憑證** | 嚴禁將 SSH 私鑰或 API Token 存入 Git；所有工具直接整合本機 `~/.ssh/` 與 `ssh-agent`。 |
| **INV-03** | **三層分離架構** | 嚴格區分不可變動之 `core` 規格、宣告式 `site` 站點意圖與動態 `node` 遙測事實。 |
| **INV-04** | **真實感官遙測** | 硬性不變量由 `schema/*.cue` 驗證；節點硬體與狀態一律即時探測並儲存為純 JSON（`conf/nodes/*.json`）。 |

## Wiki 目錄導覽

* **[系統架構](./architecture)** — 三層分離、4 庫聯邦權限隔離、Flat LAN 網段與 CUE 約束模型。
* **[安全政策與金鑰生命週期](./security)** — 語意金鑰角色、三階段零停機輪替、`from="..."` 來源限制與 `lab-boot-sync` 鎖定防護。
* **[測試方法與沙箱原理](./testing)** — 正式工具驗證原則、Dagger DinD、多發行版 Docker 沙箱、PTY 模擬器與 SHA-256 災難演練。
* **[Antigravity Vibe Coding 與 AI SRE 協作](./methodology)** — 規格先行的人機協作開發流程，以及如何利用現有安全邊界讓 `AGY-Remote` 參與 SRE 維運。
* **[CLI 應用程式與內部原理](./apps/lab-init)** — 所有 `lab-*` 指令與輔助腳本的完整參數與底層運作機制。
