# lab-node 節點引導與動態納管指令手冊
> **指令名稱**：`lab-node` (或整合於 `lab-tools` 選單)  
> **所屬倉庫**：`openlab-tools`  
> **相依性**：100% Python 3 標準函式庫、本地 OpenSSH 客戶端、Gitea REST API 客戶端

---

## 1. 功能概述

`lab-node` 是叢集維運控制台專門用於 **「建立 / 刪除 / 管理 Ansible Inventory 節點 (Node Inventory Management)」** 的核心命令列工具（與單純蒐集節點詳細硬體資訊的 `node-information` / `lab-discover` 完全獨立解耦）。維運者無須手動編輯任何 YAML 設定檔或登入遠端主機手動建立使用者，即可一鍵完成：
1. 建立目標主機自動化帳號（如 `lab`）與無密碼 Sudoers 權限。
2. 注入叢集管理公鑰（開門）。
3. 探測建立 Ansible Inventory 分類所需之基本屬性（`standard`: `server`/`desktop`/`dev` 之 `os_family`, `distribution`, `capabilities`；`appliance`: `hypervisor`/`storage`）。
4. 更新本地 `conf/nodes/<hostname>.json` 與 `current.json` 節點分類快照。
5. 自動編譯產生多維度 `inventory/hosts.yml`（不觸碰 `openlab-configs/node-information/`）。
6. 觸發 Ansible 進行基礎建設標準化佈署。

---

## 2. 命令列語法與選項

```bash
lab-node <subcommand> [options]
```

### 2.1 子指令說明
* **無參數 (`lab-node`)**：啟動與 `lab-init` 共用之 `bsdinstall` 風格互動式 TUI 主控台（支援新增/救援節點、檢視節點清單、移除節點、同步重編譯 Inventory）。
* **`add`**：納管或救援目標節點（執行互動式開門、Sudo/Passphrase 救援重試、探測與註冊）。
* **`remove`**：將指定節點自 `conf/nodes/<hostname>.json` 移除並重編譯 `hosts.yml`。
* **`list`**：列出當前本地快照（`conf/nodes/current.json` 與 `/usr/local/bin/openlab/conf/current.json`）中所有已納管節點與預分類群組。
* **`sync`**：重新掃描節點分類事實並重構 `current.json` 快照與 `ansible/inventory/hosts.yml`。

### 2.2 `lab-node add` 常用參數
```bash
# 互動模式 (推薦：引導輸入目標 IP 與初始密碼)
lab-node add 192.168.1.245

# 指定初始連線使用者 (預設 root)
lab-node add 192.168.1.245 -u ubuntu

# 指定 SSH 連線埠號
lab-node add 192.168.1.245 -p 2222

# 指定欲建立之自動化帳號名稱 (預設繼承 cluster.ansible_user: lab)
lab-node add 192.168.1.245 --automation-user lab
```

---

## 3. TUI 互動引導流程展示

當在終端執行 `lab-node add 192.168.1.245` 時：

```text
================================================================================
  🚀 OpenLabOps Node Onboarding Wizard (lab-node add)
================================================================================
  [目標位址]   : 192.168.1.245:22
  [登入帳號]   : root
  [開門目標]   : 建立帳號 'lab' 並寫入 ~/.ssh/lab.pub
  ──────────────────────────────────────────────────────────────────────────────
  [1/5] 連線至目標主機...
        (請於下方輸入目標機器初始密碼，金鑰認證將自動略過)
  root@192.168.1.245's password: ********

  [2/5] 執行開門腳本 (bootstrap-probe.sh)...
        • 建立系統帳號 'lab' (Linux 相容) ... [OK]
        • 建立 /etc/sudoers.d/lab (NOPASSWD) ... [OK]
        • 寫入 /home/lab/.ssh/authorized_keys ... [OK]
        • 驗證 OpenSSH 守護行程運行 ... [OK]

  [3/5] 採集現場事實 (Sensory Probing)...
        • 作業系統 : VMware Photon OS 5.0 (Linux x86_64)
        • 硬體規格 : 4 Cores, 8192 MB RAM, 64 GB Storage
        • 網路子網 : 192.168.1.245/24 (網關: 192.168.1.254)
        • 容器能力 : Docker-CE 24.0.5 已就緒

  [4/5] 預分類與本機快照更新...
        • 命中作業系統群組 : [photonos]
        • 命中網路服務群組 : [service_lan]
        • 命中容器能力群組 : [docker_hosts]
        • 寫入快照 : /usr/local/bin/openlab/conf/current.json ... [OK]

  [5/5] 編譯更新 Ansible Inventory...
        • 寫入節點分類檔 : conf/nodes/k8s-node-01.json ... [OK]
        • 自動編譯更新 : ansible/inventory/hosts.yml ... [OK]
================================================================================
  🎉 [納管成功] 節點 k8s-node-01 (192.168.1.245) 已完成開門並加入集群！
  💡 提示: 您現在可立即執行 Ansible 或於 lab-tools 檢視全網儀表板。
================================================================================
```

---

## 4. `lab-tools` 主選單整合

在 `lab-tools` 主控制台選單中，正式加入第 `[6]` 項節點生命週期管理：

```text
============================================================
  OpenLabOps Cluster Management Console (lab-tools) v0.2.0
============================================================
  [1] 叢集整體狀態儀表板 (lab-status)
  [2] 跨節點套件檢查與升級 (lab-upgrade)
  [3] 互動式 SSH 叢集連線器 (lab-ssh)
  [4] 節點硬體與網路詳細審計 (lab-info)
  [5] 叢集備份管理套件 (lab-backup)
  [6] 節點動態納管與引導 (lab-node add / list)  <-- NEW
  [7] 叢集管理金鑰輪換套件 (lab-rotate-keys)
  [0] 離開控制台 (Exit)
============================================================
```

---

## 5. 安全與零信任防護機制

1. **無密碼安全憑據與即時 PTY 密碼攔截**：整個過程優先使用本機既有金鑰與 `.gitea_token`，絕不將任何密碼暫存於硬碟或腳本中。若遠端需要 Sudo 密碼或私鑰 Passphrase，透過記憶體內即時攔截輸入直接送入 PTY 虛擬終端，執行完畢即刻清除。
2. **開門限制 (IP Option)**：寫入目標節點的公鑰可指定帶有 `from="<service_lan>,<wg_lan>"` 網段限制，防止非授權 IP 利用開門金鑰登入。
3. **Sudoers 安全語法檢驗**：寫入 `/etc/sudoers.d/lab` 時，強制以 `visudo -cf` 進行語法檢驗，若語法錯誤立刻還原，絕不損壞遠端機器之提權機制。
