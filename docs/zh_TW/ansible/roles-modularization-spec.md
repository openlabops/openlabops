# Ansible 角色積木化與參數解耦規格書 (Roles Modularization Specification)
> **規範層級**：Ansible IaC 核心架構標準  
> **適用範圍**：`openlab-ansible` 儲存庫與 OpenLabOps 開源體系  
> **目標**：將原先單體化、重複編寫之 Playbook 任務重構為 7 大純淨無狀態角色（Decoupled Roles），透過外部參數注入（Parameter Passing）實現極致模組化。

---

## 1. 架構演進動機與目標 (Motivation)

在重構之前，`openlab-ansible` 面臨以下架構瓶頸：
1. **任務單體化與重複宣告**：跨發行版套件安裝、SSH 強化（Port 22/2222、2FA）、使用者建立與 Sudoers 設定散落在各個 Playbook 中，維護成本高昂。
2. **硬編碼路徑依賴**：原 `roles/openlab_tools` 與特定主機名稱綁定，無法直接移植至 OpenLabOps 開源社群。
3. **缺乏積木化組合能力**：Playbook 無法透過簡單的宣告式角色組合（Role Composition）拼裝出不同生命週期的維運任務。

重構後之核心原則：
* **角色純淨無狀態 (Stateless Roles)**：角色本身僅定義任務邏輯與預設值（`defaults/main.yml`），所有站點特異性參數皆由外部傳入。
* **發行版感知與自適應 (Distro-Aware)**：全面支援 PhotonOS、ArchLinux、Debian/Ubuntu、Oracle Linux/RHEL、Alpine 與 openSUSE。
* **冪等性保證 (Strict Idempotency)**：所有任務具備嚴格的 `creates=`, `stat:`, `when:` 檢查條件與事件觸發器（Handlers）。

---

## 2. 7 大標準解耦角色拓撲

```text
openlab-ansible/roles/
├── baseline/                   # 系統基礎基線 (Python 啟動、套件、時區、sshd 強化、2FA)
├── users/                      # 資料驅動帳號管理 (自動化帳號、sudoers 免密、公鑰注入)
├── dotfiles/                   # 跨平台個人化環境 (Shell, Editor, SSH Config 部署)
├── tools/                      # 通用維運工具鏈部署 (前身為 openlab_tools，已通用化)
├── docker_runtime/             # 容器運行時維運 (Compose 目錄、Git Post-Push Hook、Pull)
├── ssh_keys/                   # 全網金鑰管理 (節點公私鑰、端點公鑰部署/吊銷、三階段輪換)
└── gateway/                    # 核心閘道專用 (PF 防火牆、dnsmasq 備份)
```

---

## 3. 各角色職責與介面規格

### 3.1 `roles/baseline` (系統基礎與安全基線)
* **職責**：
  - 針對無 Python 環境之裸機執行 raw bootstrap 安裝 Python。
  - 跨發行版安裝通用基礎套件（`tdnf`, `pkg`, `pacman`, `dnf`, `apt`, `apk`, `zypper`）。
  - 配置全域標準時區（預設 `UTC`）與 NTP/Chronyd 同步。
  - SSH Daemon 安全基線強化：
    - 支援標準埠號（22）與高防安全埠（2222）。
    - 密碼登入停用（`PasswordAuthentication no`）、Root 遠端登入限制。
    - Google Authenticator 2FA 模組與 PAM 整合（具備 `reload sshd` 觸發器）。
* **重要參數**：
  ```yaml
  system_timezone: "UTC"
  sshd_port: 22
  sshd_enable_2fa: false
  sshd_password_auth: "no"
  ```

---

### 3.2 `roles/users` (資料驅動帳號管理)
* **職責**：
  - 根據傳入之使用者字典清單建立系統帳號、UID/GID、主群組與附屬群組。
  - 動態配置 `/etc/sudoers.d/<username>`（權限 `0440`，經 `visudo -cf` 驗證）。
  - 安全建立 `.ssh/` 目錄（`0700`）並寫入具備來源 IP 白名單限制（`from="..."`）之 `authorized_keys`（`0600`）。
* **重要參數**：
  ```yaml
  manage_users:
    - name: "ansible"
      group: "wheel"
      sudoer_nopasswd: true
      ssh_keys:
        - key: "{{ ansible_pubkey }}"
          options: 'from="192.168.1.0/24"'
  ```

---

### 3.3 `roles/dotfiles` (跨平台環境部署)
* **職責**：
  - 自配置倉庫分發 Shell 配置：`.zshrc`, `.bashrc`, `.cshrc`（BSD 專用）。
  - 分發 Neovim (`~/.config/nvim/`)、NvChad 與 Vim 配置。
  - 分發本機 OpenSSH 客戶端別名設定（`~/.ssh/config`）。
* **重要參數**：
  ```yaml
  dotfiles_deploy_shell: true
  dotfiles_deploy_editor: true
  dotfiles_target_user: "admin"
  dotfiles_source_path: "{{ playbook_dir }}/../../openlab-configs"
  ```

---

### 3.4 `roles/tools` (通用維運工具鏈)
* **職責**：
  - 統一安裝與升級通用 CLI 維運工具庫（`lab-tools`, `lab-status`, `lab-node`, `lab-ssh` 等）。
  - 標準化安裝路徑至 `/usr/local/bin/{{ tools_suite_name }}/`。
  - 於 `/usr/local/bin/` 建立所有 CLI 的全域符號連結（Symlinks）。
  - 清理舊版廢棄指令與目錄，維持環境乾淨。
* **重要參數**：
  ```yaml
  tools_suite_name: "openlab"
  tools_install_dir: "/usr/local/bin/openlab"
  bin_symlink_dir: "/usr/local/bin"
  ```

---

### 3.5 `roles/docker_runtime` (容器運行時與 GitOps 整合)
* **職責**：
  - 確保受控節點之 Docker Compose 專用目錄存在。
  - 部署遠端 Git Post-Push Hook（`0755`），實現「本機推代碼 $\rightarrow$ 遠端自動重載容器」。
  - 執行 `git pull` 與 `docker compose up -d` 滾動重啟。
* **重要參數**：
  ```yaml
  docker_compose_dir: "/home/labadmin/docker-compose"
  docker_install_hook: true
  ```

---

### 3.6 `roles/ssh_keys` (全網金鑰維運與三階段輪換)
* **職責**：
  - 分發受控節點金鑰至控制端與授權節點。
  - 部署端點使用者公鑰至目標伺服器之 `authorized_keys`。
  - 執行全網公鑰撤銷與清理。
  - **三階段零停機金鑰輪換**（Stage 1: 追加新金鑰 $\rightarrow$ Stage 2: 驗證新金鑰連通性 $\rightarrow$ Stage 3: 安全移除舊金鑰）。
  - **專用設備開門與固化**：
* **重要參數**：
  ```yaml
  key_rotation_stage: "stage1_add"   # stage1_add | stage2_verify | stage3_remove
  target_key_name: "openlab"
  ```

---

### 3.7 `roles/gateway` (核心閘道專用)
* **職責**：
  - 備份與校驗 核心 Gateway 之 PF 防火牆設定（`/etc/pf.conf` 與 `/etc/pf.conf`）。
  - 備份 DHCP 靜態租約與 dnsmasq 配置。
* **重要參數**：
  ```yaml
  gateway_backup_dest: "{{ playbook_dir }}/../../openlab-configs/network/gateway"
  ```

---

## 4. Playbooks 積木化組合範例

在重構後的 Playbook 中，劇本僅負責宣告目標主機、提權與呼叫對應的角色：

```yaml
# playbooks/node-provisioning.yml 範例
---
- name: "Phase 1: 基礎系統基線建置"
  hosts: "{{ target_hosts | default('servers') }}"
  become: true
  roles:
    - role: baseline

- name: "Phase 2: 標準自動化帳號與安全防護"
  hosts: "{{ target_hosts | default('servers') }}"
  become: true
  roles:
    - role: users
      vars:
        manage_users:
          - name: "{{ cluster_ansible_user | default('lab') }}"
            group: "{{ 'wheel' if ansible_system == 'BSD' else 'root' }}"
            sudoer_nopasswd: true

- name: "Phase 3: 工具鏈與環境配置"
  hosts: "{{ target_hosts | default('servers') }}"
  roles:
    - role: dotfiles
    - role: tools
```

---

## 5. 驗證與品質保證

所有 19 個 Playbook 均通過語法與角色解析驗證：
```bash
ansible-playbook -i inventory/hosts.yml --syntax-check playbooks/*.yml
# 執行結果：19/19 通過，0 錯誤，0 警示
```
