---
id: architecture
title: 系統架構
sidebar_position: 2
---

# 系統架構

OpenLabOps 透過嚴格的職責分離，將「不可變動框架合約」、「站點宣告式意圖」與「即時節點遙測」切分為三層，並映射到四個職責隔離的下游 GitOps 倉庫。

```mermaid
flowchart TB
    subgraph Console["控制端工作站 (~/.ssh Agent)"]
        CLI["零依賴 Python CLI<br/>lab-init / lab-node / lab-status / lab-tools"]
        T1["Tier 1: 核心規格<br/>conf/core.manifest.yml + schema/*.cue"]
        T2["Tier 2: 站點意圖<br/>conf/openlab.manifest.yml"]
        T3["Tier 3: 節點遙測<br/>conf/nodes/*.json"]
    end

    subgraph Federation["四庫聯邦 GitOps 架構"]
        OPS["openlab-operations<br/>Playbooks + 引擎"]
        WF["openlab-workflows<br/>CI/CD + Runner 派發"]
        CFG["openlab-configs<br/>CMDB + 節點事實"]
        SEC["openlab-secrets<br/>加密保險庫 + 公鑰"]
    end

    subgraph Fleet["受管 Flat LAN 集群 (192.168.1.0/24)"]
        N1["伺服器節點<br/>Arch / Debian / Ubuntu"]
        N2["開發與桌面工作站<br/>Workstations + 開機同步防護"]
        N3["容器與輕量節點<br/>Alpine / Photon / Docker"]
    end

    CLI --> T1 & T2 & T3
    T3 -->|"編譯 hosts.yml"| OPS
    CLI -->|"派發工作流 (ci-bot)"| WF
    WF -->|"唯讀檢出"| OPS
    WF -->|"推送遙測與手冊"| CFG
    WF -->|"讀取金鑰策略"| SEC
    WF -->|"透過 SSH 執行 Ansible"| Fleet
```

## 1. 三層分離模型

1. **Tier 1 (`core`)：不可變動之框架規格**
   * 定義於 `conf/core.manifest.yml` 與 `schema/*.cue`。
   * 規範四庫聯邦拓撲、三大標準金鑰角色（`ansible`、`user`、`git`）、安全基線與 CUE 約束規則。
2. **Tier 2 (`site`)：站點宣告式意圖**
   * 定義於 `conf/openlab.manifest.yml`。
   * 儲存集群名稱、網域、Flat LAN 子網（`192.168.1.0/24`）、閘道器、管理員與 Ansible 帳號及 Gitea 端點。如同 `archinstall`，預設由 `lab-init` 互動精靈動態產生，並匯出供無人值守重現。
3. **Tier 3 (`node`)：動態機器遙測事實**
   * 儲存於 `conf/nodes/*.json`（庫存分類）與 `node-information/node_<hostname>.json`（CMDB 硬體、容器與金鑰事實）。
   * 嚴禁寫死於靜態 Manifest；一律由 `lab-node` 與 `lab-discover` 即時探測，並由 `engine/classifier.py` 編譯為 `ansible/inventory/hosts.yml`。

## 2. 四庫聯邦與爆破半徑隔離

為避免 CI/CD Token 遭濫用而篡改 IaC 程式碼，OpenLabOps 將下游倉庫拆分為四個獨立庫：

* **`openlab-operations`**：存放 Ansible 劇本、Roles、引擎與 CLI 工具。
* **`openlab-workflows`**：存放 Gitea Actions 工作流。自動化帳號（`ci-bot`）權限嚴格受限於此，**物理上無法修改** `openlab-operations`。
* **`openlab-configs`**：存放節點硬體事實（`node-information/node_*.json`）、套件清單與自動產生的 Markdown 節點手冊。
* **`openlab-secrets`**：存放公鑰、端點金鑰註冊表與加密機密。

## 3. Flat LAN 與多發行版 Linux 支援

* **網路規格 (`schema/network.cue`)**：專為標準單一子網（`192.168.1.0/24`）設計，並透過 CUE 阻擋子網重疊或無效閘道設定。
* **支援發行版**：原生支援 **Arch Linux**、**Debian**、**Ubuntu**、**Oracle Linux**、**Alpine Linux**、**VMware Photon OS** 與通用 systemd Linux 主機。

## 4. 零依賴 Python 引擎與中央執行架構

所有控制台與端點 CLI（`bin/lab-*` 與 `tools/bin/lab-*`）皆共用 `tools/lib/core/`（`config.py`、`yaml_parser.py`、`gitea_api.py`、`live_probe.py`、`lockout.py` 等），100% 以 Python 3 標準函式庫撰寫。端點無須安裝 Ansible，所有劇本統一由 Gitea Act Runner 容器集中執行。
