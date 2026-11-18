# Homelab Ansible - 基礎設施自動化與架構規範文件

本專案負責整個 OpenLabOps Homelab 基礎設施的組態管理（Configuration Management）、自動化運維（Automation）與群組變數調度。

---

## 1. 核心哲學與原則 (System Philosophy)

1. **Gitea Actions 擔任中央 Ansible Server (Central Automation Hub)**：
   - 由 Gitea Actions Runner 擔任調度中樞與金鑰權限中心 (Key Authority)。
   - 對於全網 7/24 常態在線之伺服器群 (`servers`)，一律透過 Gitea Actions 以 `lab` 帳號執行中央無狀態推送 (Central Stateless Push)。
2. **極簡本機依賴與 Playbook 驅動萬物 (Minimal Edge Footprint & Playbook-Driven)**：
   - 外部非 7/24 端點（如 `laptop`、`workstation` 等端點）本機**僅保留最小必要功能**：
     - 本機生成帶 Passphrase 保護之金鑰對（確保私鑰永不離開本機，落實零私鑰託管）。
     - 本地儲存與讀取 Gitea Token 檔（`/usr/local/bin/openlab/.gitea_token`，權限 `0600`）。
     - 呼叫 Gitea REST API 發送 Dispatch 觸發工作流。
   - **除上述本機必要操作外，所有環境設定、工具安裝與節點設定一律透過 Ansible Playbook 作動**。
3. **外部端點之自舉安裝 (Endpoint Self-Bootstrapping via `ansible-pull`)**：
   - 外部端點因處於動態網路或休眠狀態，無法由中央隨時主動推入。
   - 端點在自身「環境設定與工具安裝」階段，由本機自主執行 `ansible-pull` 拉取 `openlab-ansible` 內之專用劇本，將 `openlab-tools` 與執行環境自動配置於 `/usr/local/bin/openlab/`。
4. **API 命令聯動機制 (API-Driven Delegation)**：
   - 外部端點完成本機工具安裝與金鑰生成後，透過本機工具讀取 Token 發送 Dispatch API 委派 Gitea Actions。
   - Gitea Actions 接手後，依據倉庫內指定之 Playbook 執行跨節點部署（例如部署端點公鑰至全網伺服器之 `labadmin` 帳號）。
5. **資料與邏輯解耦 (Repository Decoupling)**：
   - Ansible Playbook (邏輯)、Configs/Node Specs (狀態與公鑰)、Workflows (流程調度) 分拆三庫管理。
6. **帳號權限嚴格隔離 (Account Privilege Isolation)**：
   - **`lab` 帳號**：專屬於 Ansible 自動化運維與 CI/CD 執行，全域使用 `ansible.key` 免密連線，嚴禁混用為一般使用者連線，保留為災難救援通道。
   - **`labadmin` 帳號**：專屬於管理者與內部節點通用 SSH 登入，支援端點公鑰登入與可選之 2FA 密碼雙重認證。
   - **`id_user.key`**：全網最高權限萬能管理金鑰 (Universal Master Admin Key)，用於管理者統籌管理整個 Homelab 及 OpenLabOps 基礎設施。在底層封閉韌體設備 (`appliances`: Storage 儲存、Virtualization 宿主機) 上，為**唯一被允許存取**之 SSH 金鑰 (user: root)，並嚴格限制僅允許自內部網管網段 `192.168.1.0/24` 存取。


---

## 2. 三庫職責分工 (Repository Architecture)

- **`openlab-ansible`**：全局調度邏輯、Roles、Inventory 拓撲、Group/Host Vars 與架構規範 (本庫)。
- **`openlab-configs`**：靜態與動態配置庫、SSH 公鑰檔 (`ssh-key/*.pub`)、網路組態與節點狀態手冊。
- **`openlab-workflows`**：集中定義的 CI/CD 流水線，透過 Actions Bot 自動同步執行。

---

## 3. 專案目錄結構 (Directory Structure)

```
openlab-ansible/
├── inventory/                  # 主機拓撲清單目錄
│   └── hosts.yml              # 集中式 YAML 主機清單與五層級群組結構
├── group_vars/                 # 群組共享變數目錄 (Group Shared Variables)
│   ├── all.yml                # 全域預設變數 (ansible_user: lab, ssh_key, timezone)
│   ├── servers.yml            # 24/7 伺服器群組變數 (monitoring, backup)
│   ├── openlab.yml          # OpenLabOps 網段群組變數 (allowed_ssh_cidrs)
│   ├── homelab.yml            # Homelab 本地網段變數 (subnet, local_dns)
│   ├── bsd.yml            # BSD OS 變數 (python3.11, pkg)
│   ├── photonos.yml           # Photon OS 變數 (python3.14, tdnf)
│   ├── oci.yml                # Oracle Linux 變數 (python3.12, dnf)
│   └── archlinux.yml          # Arch Linux 變數 (pacman)
├── host_vars/                  # 主機專屬變數目錄 (Host Specific Variables)
│   ├── workstation.yml, laptop.yml     # 獨立端點主機變數
│   ├── srv-node1.yml, gw-node.yml      # 核心伺服器變數
│   └── cloud-node1.yml                 # 雲端節點變數
├── vars/                       # 中央劇本與專案金鑰規格目錄 (Central Playbook Vars)
│   ├── main.yml               # 專案索引與全域變數
│   └── ssh_keys.yml           # SSH 金鑰輪換中央規格 (lab, openlab, git_openlab)
├── playbooks/                  # 自動化任務劇本目錄
│   ├── endpoint-setup.yml     # [端點自舉] 外部端點 ansible-pull 本機環境設定與工具安裝劇本
│   ├── node-provisioning.yml  # [伺服器納管] 7/24 伺服器節點由 Gitea Actions 執行全自動安裝與基線設定
│   ├── rotate-lab-keys.yml   # Lab Key (Ansible) 三階段輪換 Playbook
│   ├── rotate-openlab-keys.yml # OpenLabOps Key 三階段輪換 Playbook
│   ├── pull-docker-compose.yml# Git Pull Docker Compose 部署劇本
│   ├── install-docker-compose-hook.yml # 安裝 Git Post-Push Hook 劇本
│   ├── deploy-host-key.yml    # 部署通用端點公鑰 ($hostname.pub) 至伺服器 labadmin 帳號劇本
│   └── deploy-dotfiles.yml    # [環境部署] 跨平台同步 Shell 與 Editor 設定至全網節點劇本
├── roles/                      # 可複用 Ansible Roles (預留)
└── docs/                       # 專案說明文件庫
    ├── architecture.md         # 本架構規範文件
    ├── endpoint-bootstrap.md   # 外部端點 (WSL/筆電) ansible-pull 與工具安裝標準規範
    ├── node-provisioning.md    # 7/24 伺服器節點自動化安裝與基線調優規格文件
    ├── inventory.md            # 主機與變數詳細解說
    └── playbooks.md            # Playbooks 執行與 Tags 說明
```

---

## 4. 自動化與變數管理原則 (Automation & Variable Principles)

1. **變數引用與繼承機制 (Group Vars & Host Vars Integration)**：
   - **`group_vars/`**：同屬群組（OS Distro, 網段, 24/7 Server）共享預設值（例如 SSH 帳號 `lab`、Python 解譯器路徑、預設套件管理員）。
   - **`host_vars/`**：單一主機之獨立屬性（如 `ansible_host` IP、FQDN `hostname`）。
   - **主機引用群組方式**：各 Host 透過在 `inventory/hosts.yml` 中隸屬特定群組，自動引用並繼承 `group_vars/` 設定。
2. **中央金鑰與劇本變數 (`vars/`)**：`vars/ssh_keys.yml` 與 `vars/main.yml` 提供 Playbooks 跨主機共用的 central key definitions。
3. **冪等性與安全性 (Idempotency & Access Control)**：
   - 強制宣告 `key_options: 'from="..."'` 限制允許連線的來源 IP 網段。
   - 金鑰輪換區分為 3 個標準 Tags (`add_new_key`, `verify_new_key`, `remove_old_key`)，先驗證後移除舊 Key。
