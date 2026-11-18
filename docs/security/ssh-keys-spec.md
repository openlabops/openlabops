# 全網 SSH 金鑰定義與安全連線總規範 (ssh-keys-spec.md)

本文件整合 OpenLabOps 體系全網所有 SSH 金鑰對（自動化 Master Key、通用連線 Key、Git 版控 Key、端點工作站 Key）之安全屬性、產製位置、存取權限與安全隔離原則。

> [!IMPORTANT]
> **單一真理源宣告 (SSOT)**：
> 全網核心聚焦於三大無密碼語意金鑰角色 `keys:` (`ansible: ansible.key`, `user: id_user.key`, `git: git.key`) 及因應 Generic Linux 協定限制之 `ansible.key`（其他外部含密碼金鑰列為後續擴充 Pending）。金鑰規格模板定義於 [conf/core.manifest.yml](../../conf/core.manifest.yml) 與 [schema/roles.cue](../../schema/roles.cue)。

---

## 1. 核心安全哲學與權限隔離原則 (Security Principles)

1. **Ansible 帳號獨立性 (`lab`)**：
   - `lab` 帳號專屬於 **Ansible 自動化運維與 CI/CD 執行**。
   - 僅允許 `lab.pub` 寫入受控主機之 `lab` 帳號，**嚴禁**將個體端點公鑰（如 `endpoint.pub`）部署至 `lab` 帳號。
2. **個人端點公鑰目標 (`labadmin`)**：
   - 所有個人端點公鑰（`$hostname.pub`）統一步署至目標伺服器之 **`labadmin`** 使用者帳號。
3. **私鑰極小化 (Zero Credential on Edge Repos)**：
   - 本地端點私鑰 (`$hostname.key` / 如 `endpoint.key`) 僅留存於各自端點本機發源地 (Origin Host)，**絕不上傳或託管**於儲存庫中。
   - 控制台運維工具直接使用 Console (`control-node`) 本機 `~/.ssh/` 之金鑰，倉庫內不存放任何明文私鑰。
4. **OCI 網路方向與單向防護障壁**：
   - OCI 雲端網段 (`openlab_mesh`: `192.168.1.0/24`) 僅提供對外服務，**嚴格禁止反向 SSH 連回** 本地核心服務網段 (`service_lan`: `192.168.1.0/24`)。
   - OCI 節點上的公鑰來源白名單遵循 Gateway 外網固定出口 IP 區段 (`198.51.100.10/32`) 與 WireGuard Mesh 網段 (`192.168.1.0/24`)。
5. **檔案系統權限強制規範**：
   - 私鑰檔 (`*.key`)：系統載入或產生時強制權限為 **`0600`** (`-rw-------`)。
   - 公鑰檔 (`*.pub`)：權限設定為 **`0644`** (`-rw-r--r--`)。
   - SSH 目錄 (`~/.ssh`)：嚴格限制為 **`0700`** (`drwx------`)。

---

## 2. 金鑰分類與職責總覽 (Key Archetypes)

| 金鑰種類 | 宣告參數鍵名 | 預設演算法 | 目標受控帳號 | 來源 IP 限制 (ACL) | 核心職責 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ansible 自動化金鑰** | `keys.ansible` (`ansible.key`) | Ed25519 | `lab` | `service_lan` (`192.168.1.0/24`) | 僅限 Gitea Runner 與 `dev` 節點執行 Ansible 自動化調度專用 |
| **全網管理主金鑰** | `keys.user` (`id_user.key`) | Ed25519 | `labadmin` *(Storage: `root`)* | `service_lan`, `user_lan`, `wg_lan` | 內部多個 LAN 節點通用免密維運管理 (禁止 OCI 反向連回) |
| **Virtualization 宿主機金鑰** | `ansible.key` (`standard`) | RSA / ECDSA-384 | `root` | `service_lan` (`192.168.1.0/24`) | Generic Linux 宿主機管理專用 (隨主金鑰同週期輪換) |
| **本地 Git 版控金鑰** | `keys.git` (`git.key`) | Ed25519 | `git` (API) | 無限制 | 本地主機向 Gitea / GitHub 提送代碼之通用憑據 |
| **外部含密碼端點金鑰** | *(Pending 後續擴充)* | Ed25519 | `labadmin` | `wg_lan` (`192.168.1.0/24`) | 外部端點擴充保留項 |

---

## 3. 金鑰自動化輪換標籤標準 (Key Tagging Convention)

每次自動化或工具腳本生成金鑰時，`-C` 參數必須包含明確的識別名稱與產出時間戳記（精確至年月日時分）：
* `lab-ansible-YYYYMMDDHHMM`
* `openlab-YYYYMMDDHHMM`
* `kvm-YYYYMMDDHHMM`
* `git-openlab-YYYYMMDDHHMM`
* `$hostname-client-YYYYMMDDHHMM`

---

## 4. 全節點 Git SHA 索引開機同步與門禁機制（分散控制 + 集中分發）

1. **分散控制 + 集中分發 (CI-Bot Token 邊界)**：
   - 為兼顧各節點自主觸發與中央集中派發，受控節點配置受限的 `ci-bot` Token（僅用於觸發固定的 Gitea API Workflow，而非無限制執行任意 Playbook）。
2. **開機比對與舊版私鑰開門流程**：
   - 所有受控節點（`server` 與 `desktop`）皆可能因停機而錯過金鑰輪替。
   - 節點開機時由 `lab-boot-sync` 比對本機 `/etc/openlab/last_synced_commit` 與遠端 `openlab-secrets` 倉庫最新 Commit SHA。
   - 若版號不一致，節點透過 `ci-bot` Token 觸發 `deploy-ssh-keys.yml` 並傳入本機舊版 `source_commit_sha`；Gitea Runner 執行 `git show <old_sha>:ssh-key/ansible.key` 取出該節點停機前的舊私鑰開門，依標準 Rotate 流程部署最新公鑰、移除舊公鑰並更新本機 `/etc/openlab/last_synced_commit`（無須重新生成金鑰對）。
3. **開機門禁 (`/run/openlab/synced_ok`)**：
   - 在開機同步完成並建立 `/run/openlab/synced_ok`（`tmpfs` 記憶體標記，重開機自動清空）前，節點上的 `lab-*` 工具自動阻斷所有涉及遠端連線之維運操作。
