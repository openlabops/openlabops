# Playbooks 劇本與 Tags 說明文件

本文件詳細解說 [playbooks/](../../../ansible/playbooks) 目錄下的自動化劇本設計與執行方式。

---

## 劇本矩陣 (Playbooks Matrix - 20 Standard Playbooks)

| 劇本名稱 | 呼叫解耦角色 (Composed Roles) | 目標主機 (Target) | 預設連線帳號 | 說明與階段 |
| :--- | :--- | :--- | :--- | :--- |
| **[node-provisioning.yml](../../../ansible/playbooks/node-provisioning.yml)** | `baseline`, `users`, `dotfiles`, `tools`, `docker_runtime` | `servers` | `ansible` (初始 root) | 三階段伺服器全自動化基線建立、自動化帳號與安全防護、容器環境 |
| **[deploy-ops-tools.yml](../../../ansible/playbooks/deploy-ops-tools.yml)** | `tools` | `control-node` / `servers` | `ansible` | 全網節點自動化部署中性維運工具鏈至 `/usr/local/bin/openlab/` 並建立全域軟連結 (相容別名: `deploy-openlab-tools.yml`) |
| **[endpoint-setup.yml](../../../ansible/playbooks/endpoint-setup.yml)** | `tools` | `localhost` | 本地 root/sudo | 外部端點 `ansible-pull` 自舉劇本，自動配置依賴並安裝維運工具鏈 |
| **[dev-environment.yml](../../../ansible/playbooks/dev-environment.yml)** | `tools` | `localhost` | 本地 root/sudo | 開發者工作區與 CI 沙箱環境自動化一鍵就緒自舉劇本 (`./bin/lab-dev-setup`) |
| **[deploy-dotfiles.yml](../../../ansible/playbooks/deploy-dotfiles.yml)** | `dotfiles` | `servers` | `ansible` | 跨平台部署 Shell (zsh/bash/csh) 與 Neovim/NvChad 編輯器環境 |
| **[fetch-node-configs.yml](../../../ansible/playbooks/fetch-node-configs.yml)** | `dotfiles` | 指定單一節點 | `ansible` | 從指定節點抓取最新 Shell/Editor 組態至 `openlab-configs` 供審計 |
| **[backup-node.yml](../../../ansible/playbooks/backup-node.yml)** | `dotfiles` / 系統模組 | `servers` | `ansible` | 宣告式節點關鍵設定與狀態檔案備份至 Controller Vault (支援 DR 演練) |
| **[restore-node.yml](../../../ansible/playbooks/restore-node.yml)** | `dotfiles` / 系統模組 | `servers` | `ansible` | 宣告式節點災難復原回填與權限修復 (支援 DR 位元級校驗無損還原) |
| **`backup-gateway-config.yml`** | `gateway` | `gateway` | `ansible` | 自動備份 Gateway PF 防火牆規則與 dnsmasq 租約配置 |
| **[deploy-node-ssh-keys.yml](../../../ansible/playbooks/deploy-node-ssh-keys.yml)** | `ssh_keys` | `control-node` | `ansible` | 部署各節點專屬連線私鑰與公鑰至管理機 `.ssh/` |
| **[deploy-endpoint-key.yml](../../../ansible/playbooks/deploy-endpoint-key.yml)** | `ssh_keys` | `servers` | `user` | 中性動態端點公鑰部署至全體伺服器 `authorized_keys` (相容別名: `deploy-host-key.yml`) |
| **[deploy-wsl-key.yml](../../../ansible/playbooks/deploy-endpoint-key.yml)** | `ssh_keys` | `servers` | `user` | 將 WSL 端點公鑰部署至受控伺服器 `authorized_keys` |
| **[revoke-host-key.yml](../../../ansible/playbooks/revoke-host-key.yml)** | `ssh_keys` | `servers` | `user` | 全網端點 SSH 公鑰定點清除與安全吊銷 |
| **[rotate-ansible-keys.yml](../../../ansible/playbooks/rotate-ansible-keys.yml)** | `ssh_keys` | `servers` | `ansible` | `ansible` 語意角色金鑰三階段零停機自動化輪替 (追加 $\rightarrow$ 驗證 $\rightarrow$ 移除，相容別名: `rotate-lab-keys.yml`) |
| **[rotate-openlab-keys.yml](../../../ansible/playbooks/rotate-ansible-keys.yml)** | `ssh_keys` | `servers`, `appliances` | `user` / `root` | 全網最高權限萬能金鑰輪替，支援伺服器與專用設備 (Virtualization / Storage) |
| **[collect-package-list.yml](../../../ansible/playbooks/collect-package-list.yml)** | `custom_package_facts` | `servers` | `ansible` | 跨平台採集非純相依套件清單並輸出結構化清冊至 CMDB |
| **[check-and-upgrade-packages.yml](../../../ansible/playbooks/check-and-upgrade-packages.yml)** | 系統模組 | `servers` | `ansible` | 跨平台探測 upstream 可用更新並互動確認升級系統套件 |
| **[sync-package-inventory.yml](../../../ansible/playbooks/sync-package-inventory.yml)** | 系統模組 | `servers` | `ansible` | 比對線上節點主動安裝套件 vs Repo IaC 狀態，偵測漂移並同步 |
| **[update-node-docs.yml](../../../ansible/playbooks/update-node-docs.yml)** | 系統採集 | `servers`, `appliances` | `ansible` / `root` | 全網伺服器即時硬體、網路與容器拓撲巡檢，更新 CMDB 事實文件 |

> **架構除役與邊界備註**：
> 1. `harden-ssh-2fa.yml`：經架構評審確認，在純內網環境對本機帳號套用 SSH 2FA 密碼雙認證屬於過度工程，母體貫徹集中式 SSH Agent + 零信任密鑰白名單免密通道，故自核心矩陣除役移出。
> 2. `pull-docker-compose.yml` / `install-docker-compose-hook.yml`：業務容器倉庫無須侵入維運母體，由 AGY / 本地 git 直接管理，故母體解耦除役。

---

## 全域執行效能調優規範 (Ansible Performance Tuning)

為確保在 Gitea Actions CI/CD 與本地大規模巡檢時達到極致並行與最低延遲，`openlab-ansible` 全面遵循以下效能調優規範：

### 1. `ansible.cfg` 全域加速配置
- **超並發分叉數 (`forks = 20`)**：
  - 預設值為 5，調整為 20 後，OpenLabOps 全網 12 台節點能在單一批次內 **100% 同步平行** 執行，無排隊等待。
- **SSH 管線化 (`pipelining = True`)**：
  - 繞過在遠端伺服器建立臨時 Python 模組檔案的傳統機制，直接於 SSH 管道串流執行 Python 字節碼，減少一次遠端檔案傳輸與磁碟寫入。
- **連線通道保持 (`ControlMaster=auto -o ControlPersist=120s`)**：
  - 各主機連線在 120 秒內保持長連線，重複 Task 握手耗時趨近 0ms。
- **傳輸壓縮 (`Compression=yes`)**：
  - 啟用 SSH 傳輸層壓縮，加速大檔案或複雜 Fact JSON 的跨網段回傳。
- **任務效能剖析器 (`callbacks_enabled = timer, profile_tasks`)**：
  - 每次 Playbook 執行自動於結尾打印總耗時與前 20 名最慢任務，實現視覺化效能觀測。

### 2. Playbook 任務層級最佳實務
- **Fact 採集最小化 (`gather_subset`)**：
  - 針對非重度依賴硬體的劇本（如工具鏈部署、檔案分發），宣告：
    ```yaml
    gather_subset:
      - '!all'
      - '!min'
      - 'distribution'
      - 'user'
    ```
    排除全磁碟、掛載點與網卡深層掃描，Fact 階段由 8~15 秒降至 0.8~1.4 秒。
- **批次遞迴取代迴圈 (`recurse: yes`)**：
  - 嚴格禁止對大量檔案使用 `loop` 呼叫 `file` 模組。改採目錄批次宣告：
    ```yaml
    - name: Set permissions for openlab tools
      ansible.builtin.file:
        path: /usr/local/bin/openlab
        state: directory
        mode: '0755'
        recurse: yes
    ```
    此變更在 `deploy-ops-tools.yml` (以及相容劇本) 中將檔案權限設定由 **11.86s 降至 0.86s (提速 92.7%)**。

---

## 三階段執行標籤 (Tags Specification - Key Rotation)


### 1. `add_new_key` (追加新公鑰)
- **連線憑證**：既有合法私鑰 (`ansible.key` 或 `id_user.key`)
- **任務動作**：使用 `ansible.posix.authorized_key` 模組將新生成的公鑰追加 (present) 至目標主機的 `authorized_keys`，並帶入 `key_options` 來源 IP 限制。

### 2. `verify_new_key` (驗證新私鑰)
- **連線憑證**：新私鑰 (`/tmp/ssh_rotation/ansible.key` 等)
- **任務動作**：使用 `ansible.builtin.ping` 測試新私鑰對所有目標主機的連線能力。若任何一台主機失敗，流程中斷告警。

### 3. `remove_old_key` (刪除舊公鑰)
- **連線憑證**：新私鑰
- **任務動作**：確認連線正常後，使用 `state: absent` 將舊公鑰從目標主機的 `authorized_keys` 刪除。

---

## 語法檢查與手動執行範例

### 語法檢查：
```bash
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/rotate-ansible-keys.yml
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/rotate-openlab-keys.yml
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/deploy-ops-tools.yml
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/pull-docker-compose.yml
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/install-docker-compose-hook.yml
ansible-playbook --syntax-check -i inventory/hosts.yml playbooks/deploy-wsl-key.yml
```

### 僅執行追加新 Key 階段：
```bash
ansible-playbook -i inventory/hosts.yml playbooks/rotate-ansible-keys.yml \
  --tags "add_new_key" \
  --extra-vars "new_pub_key_path=/tmp/ssh_rotation/lab.pub"
```

