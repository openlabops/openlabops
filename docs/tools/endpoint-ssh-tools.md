# 端點專屬 SSH 金鑰與連線組態工具說明文件 (Endpoint SSH Tools Specification)

本文件說明 OpenLabOps 工具鏈中的端點安全防護與組態一致性 CLI 工具：
1. **[`generate-host-ssh-key`](../../tools/bin/generate-host-ssh-key)**（實作：[`lib/generate_host_ssh_key.py`](../../tools/lib/generate_host_ssh_key.py)）：外部端點本機 Ed25519 金鑰對生成與公鑰同步工具（支援 WSL 內核自動辨識與零 Clone 模式）
2. **[`sync-ssh-config`](../../tools/bin/sync-ssh-config)**（實作：[`lib/sync_ssh_config.py`](../../tools/lib/sync_ssh_config.py)）：全網標準 `~/.ssh/config` 連線組態同步與備份工具

---

## 1. 工具一：`generate-host-ssh-key` (端點本機金鑰生成與零 Clone 部署)

### 1.1 零憑證託管哲學 (Zero Edge Credential)
依據 Homelab 全網金鑰規範，外部端點主機（如 `laptop`, `workstation`）的私鑰**絕對不經由遠端生成或託管於 Gitea**，必須在該端點本機直接生成於 `~/.ssh/`。

### 1.2 運作機制與 WSL 自動辨識
1. **本機生成帶密碼金鑰對**：
   - 生成帶有保護密碼（Passphrase）之 `ed25519` 金鑰對：
     - 私鑰儲存於 `~/.ssh/$hostname.key`，權限嚴格 `0600`。
     - 公鑰儲存於 `~/.ssh/$hostname.pub`，權限 `0644`。
2. **WSL 內核環境自動偵測**：
   - 透過 Linux 核心特徵自動探測執行環境（`/proc/version` 與 `platform.release()`）。
   - 若為 WSL 環境且主機名稱未包含 `wsl`，系統**自動為端點名稱追加 `_wsl` 後綴**（例如 `workstation` ➔ `workstation_wsl`），無須手動指定特殊參數。
3. **邊緣端點零 Clone (Zero-Clone) 模式**：
   - 非開發機器（如筆電、WSL2 等外部端點）本機無 `openlab-secrets` 或 `openlab-ansible` 倉庫，亦未安裝 `ansible-playbook`。
   - 工具自動讀取 `~/.ssh/$hostname.pub` 內容，並透過 Gitea Action Dispatch API 呼叫 `deploy-host-key.yml`（直接傳遞 `pub_key` 字串）。
   - 由 Gitea CI Runner 在隔離容器內將公鑰寫入 `openlab-secrets/ssh-key/$hostname.pub` 倉庫並提交推送，隨後調用 Ansible 自動將該公鑰寫入全網 24/7 伺服器的 `labadmin` 帳號 `authorized_keys`。
4. **開發環境本地模式**：
   - 若本機為開發工作站（具備本地 git 倉庫與 Ansible），可選擇直接執行本地 Ansible 與倉庫推送。

### 1.3 使用方式
```bash
# 在端點本機直接執行（自動辨識 WSL 並提示輸入 Passphrase，隨後派發 Gitea CI）
generate-host-ssh-key

# 明確指定端點主機名稱
generate-host-ssh-key -H workstation

# 強制重新生成金鑰對
generate-host-ssh-key --force

# 亦可透過 lab-ssh 一鍵調用
lab-ssh -g
```

---

## 2. 工具二：`sync-ssh-config` (全網標準 SSH 連線別名同步)

### 2.1 核心功能與版本分流 (Profiles)
支援依據主機角色精確分流部署 `~/.ssh/config`：
- **`openlab` (成員版)**：供內部成員/管理機使用。包含全網標準伺服器與 Appliance 設備（Storage, Virtualization），映射 `id_user.key` (萬能金鑰) 與 `ansible.key`。
- **`endpoint` (端點版)**：供外部端點 (`laptop`, `workstation`) 使用。僅包含授權端點存取之標準伺服器群，**完全排除底層 Appliance**，並使用本機獨立端點私鑰 (`~/.ssh/%h.key`)，實現零託管私鑰安全架構。

### 2.2 運作特性
1. **智慧自適配**：依據本機 Hostname 自動辨識適用版本（例如 WSL/筆電自動匹配 `endpoint`，管理機自動匹配 `openlab`）。
2. **API 直抓**：直連 Gitea REST API 獲取 `openlab-configs` 上的標準 Profile 設定檔，端點無需 Clone Git 倉庫。
3. **安全備份**：若本地現存 `~/.ssh/config` 且內容有變動，自動備份為 `~/.ssh/config.bak.<timestamp>`。
4. **嚴格權限**：寫入後自動強制設定 `~/.ssh` 為 `0700`、`~/.ssh/config` 為 `0600`。

### 2.3 使用方式
```bash
# 自動自適配同步本地 ~/.ssh/config
sync-ssh-config

# 明確指定端點版本 (外部工作站與筆電端點專用)
sync-ssh-config --profile endpoint

# 僅檢查本機組態是否漂移 (Dry-run)
sync-ssh-config --check

# 透過 lab-tools 控制台執行
lab-tools sync-ssh-config
```
