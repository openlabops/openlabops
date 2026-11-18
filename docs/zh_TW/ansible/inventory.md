# Ansible Inventory 與變數解析架構規範 (inventory.md)

本文件定義 OpenLabOps 體系中 Ansible Inventory 拓撲結構、群組階層關係、變數優先級解析（Resolution Architecture）與 SSH 來源限制機制。

> [!IMPORTANT]
> **單一事實宣告 (SSOT)**：
> 具體的主機清單、IP 位址與連線埠**不再於 Markdown 表格中硬編碼維護**。
> 所有實體定義請以 [conf/openlab.manifest.yml](../../../conf/openlab.manifest.yml) 為唯一真理源；動態硬體事實由 `node-information/` 審計抓回。

---

## 1. Inventory 拓撲與多維自動預分類階層 (Multi-Dimensional Pre-Classification)

由 [`engine/classifier.py`](../../../engine/classifier.py) 根據現場審計事實自動產出之標準階層：

```text
all
├── hosts (全網節點動態庫存)
└── children
    ├── 1. distros (作業系統分類群組 - 涵蓋 standard 類節點，隔離封閉韌體與 hypervisors)
    │   ├── archlinux      # Arch Linux (control-node, workstation1, laptop1)
    │   ├── bsd        # BSD 標準伺服器 (gw-node)
    │   ├── photonos       # VMware Photon OS 容器主機 (srv-node1, srv-node2, srv-node3)
    │   └── rhel           # Oracle Linux / RHEL 主機 (cloud-node1, cloud-node2)
    │
    ├── 2. subnets (網路拓撲與服務網段群組)
    │   ├── service_lan    # 192.168.1.0/24 (核心伺服器、開發機、儲存與虛擬化底座)
    │   ├── wg_lan         # 192.168.1.0/24 (WireGuard 管理工作站與端點客戶端)
    │   ├── openlab_mesh        # 192.168.1.0/24 (雲端網狀互聯節點)
    │   └── subnet_cloud   # 雲端公網節點
    │
    ├── 3. capabilities (節點運行能力群組)
    │   ├── docker_hosts   # 具備 Docker 運行能力之節點
    │   ├── python_hosts   # 具備原生 Python 3 執行環境之節點
    │   └── gateways       # 核心預設閘道 (gw-node)
    │
    ├── 4. dev (核心維運開發機 / 控制平面節點 - standard_role: dev)
    │   └── (control-node)
    │
    ├── 5. servers (7/24 常態在線伺服器群組 - standard_role: server)
    │   └── (srv-node1, srv-node2, srv-node3, gw-node, cloud-node1)
    │
    ├── 6. desktops (非 7/24 在線個人桌面工作站 - standard_role: desktop)
    │   └── (workstation1, laptop1)
    │
    ├── 7. appliances (封閉韌體與虛擬化宿主機 - 嚴格防禦性隔離，禁止納入 distros)
    │   ├── hypervisors    # 虛擬化宿主機總群組 (children: kvm, pve)
    │   ├── storage        # 專用儲存設備總群組 (children: storage, truenas, synology, qnap, unraid, omv)
    │   ├── kvm           # Generic Linux 虛擬化宿主機 (virt-node1)
    │   └── storage       # BSD Storage 儲存叢集 (storage1, storage2)
    │
    └── 8. endpoints (向下相容別名，指向 desktops)
        └── (workstation1, laptop1)
```

> [!CAUTION]
> **專用設備隔離鐵律 (Appliance Isolation Invariant)**：
> 1. `storage1`, `storage2`（Storage）為唯讀 Flash 嵌入式設備，**嚴禁** 納入 `distros.bsd`。
> 2. `virt-node1`（Generic Linux）為無狀態 RAMDisk 底座，**嚴禁** 納入 `distros` 或 `servers`。
> 3. 確保 `hosts: servers` 或 `hosts: distros` 的維運劇本（如 `node-provisioning.yml`, `check-and-upgrade-packages.yml`）永遠不會對專用設備派發不相容的套件管理指令。

---

## 2. 變數結構與引用機制 (Variables & Resolution Architecture)

本專案採用 **Group Vars 共享 + Host Vars 專屬** 之雙層變數目錄架構：

1. **`group_vars/` (群組共享變數)**：
   - `group_vars/all.yml`：`ansible_user: lab`, `ansible_ssh_private_key_file: ~/.ssh/ansible.key`, 全域時區與語系。
   - `group_vars/servers.yml`：7/24 在線標準伺服器共用設定 (`is_24_7_server: true`, `monitoring_enabled: true`)。
   - `group_vars/appliances.yml`：底層封閉韌體通用變數 (`user_key_options`)。
   - `group_vars/openlab.yml`：OpenLabOps 網段 CIDR 與 SSH 允許白名單。
   - `group_vars/homelab.yml`：Homelab 本地網段設定 (`192.168.1.0/24`)。
   - Distro 群組：`bsd.yml`, `photonos.yml`, `oci.yml`, `archlinux.yml`, `storage.yml` 定義各自連線與執行環境。
2. **`host_vars/` (主機專屬變數)**：
   - 每台主機皆有獨立的 `host_vars/<hostname>.yml` 檔案（例如 `host_vars/gw-node.yml`, `host_vars/srv-node1.yml`）。
   - 僅記錄主機特有設定，如 `ansible_host` IP 地址與專屬 FQDN。
3. **主機引用 Group Vars 方式**：
   - 主機透過在 `inventory/hosts.yml` 中隸屬於特定群組，由 Ansible 自動載入該群組對應之 `group_vars/<group_name>.yml`。
   - 主機變數 (`host_vars/`) 可隨時覆蓋群組共享變數 (`group_vars/`)，維持靈活彈性與高內聚性。

---

## 3. SSH 來源 IP 白名單 (`from=""`) 規範

在受控節點的 `authorized_keys` 中，所有金鑰均自動注入嚴格的 `from="..."` 來源 IP 白名單防護：

* **Ansible 自動化帳號 (`lab`)**：
   - 本地節點限制僅允許來自 `service_lan` (`192.168.1.0/24`)。
   - OCI 跨網節點允許來自 `service_lan`、`openlab_mesh` 與 Gateway 外網固定 IP (`198.51.100.0/24`)。
* **管理員主金鑰 (`id_user.key`)**：
  - 限制來自 `service_lan`、`user_lan` 及 `openlab_mesh`。
  - 嚴禁外部/雲端跨網網段反向連回內網。
* **個人端點金鑰 (`$hostname.key`)**：
  - 僅允許透過 WireGuard 管理網段 (`wg_lan`: `192.168.1.0/24`) 接入，且僅能登入 `labadmin` 帳號。
* **韌體設備例外規則**：
