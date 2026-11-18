# 套件清冊採集、升級與 IaC 同步劇本說明文件 (Package Management & IaC Playbooks)

本文件解說 OpenLabOps Homelab 針對軟體套件管理的完整自動化劇本體系，包含：
1. **[`collect-package-list.yml`](../../../../ansible/playbooks/collect-package-list.yml)**：全網節點主動安裝套件清冊採集
2. **[`check-and-upgrade-packages.yml`](../../../../ansible/playbooks/check-and-upgrade-packages.yml)**：跨平台新版本檢測與互動式升級維護
3. **[`sync-package-inventory.yml`](../../../../ansible/playbooks/sync-package-inventory.yml)**：Repo IaC (`host_vars`) 漂移比對與雙向同步

---

## 1. 劇本一：`collect-package-list.yml` (套件清冊採集)

* **目標主機**：`servers`（正向疊加模型，專屬標準作業系統伺服器群）
* **核心機制**：
  - 調用 [`custom_package_facts`](../../../../ansible/library/custom_package_facts.py) 模組，傳入 `filter_dependencies: true` 與 `filter_system: true`。
  - 將各節點的非相依、非系統主動安裝套件以結構化 JSON 匯出至 `openlab-configs/node-information/packages_<hostname>.json`。
* **執行命令**：
  ```bash
  ansible-playbook -i inventory/hosts.yml playbooks/collect-package-list.yml
  ansible-playbook -i inventory/hosts.yml playbooks/collect-package-list.yml -e "target_hosts=srv-node1"
  ```

---

## 2. 劇本二：`check-and-upgrade-packages.yml` (套件升級比對與執行)

* **目標主機**：`servers`（正向疊加模型，專屬標準作業系統伺服器群）
* **核心機制**：
  - 調用 `custom_package_facts: check_upgrades: true`，探測 upstream 是否有可升級的新版套件。
  - 若有可用更新，終端清楚列出套件名稱、目前版本、新版本與來源庫。
  - 透過 `ansible.builtin.pause` 互動暫停詢問：
    `[節點 <hostname>] 檢測到 N 個套件可升級。是否立即執行套件升級？ (輸入 'yes' 確認執行，其餘任意鍵略過):`
  - 確認後依照 Distro 原生命令執行更新（Arch 透過一般使用者執行 `yay -Syu --noconfirm --needed`，BSD 執行 `pkg upgrade -y`，PhotonOS 執行 `tdnf update -y`，Oracle Linux 執行 `dnf upgrade -y`）。
* **執行命令**：
  ```bash
  # 互動模式 (預設，人為逐一確認)
  ansible-playbook -i inventory/hosts.yml playbooks/check-and-upgrade-packages.yml

  # CI/CD 免互動自動更新模式
  ansible-playbook -i inventory/hosts.yml playbooks/check-and-upgrade-packages.yml -e "auto_upgrade=true"
  ```

---

## 3. 劇本三：`sync-package-inventory.yml` (IaC 漂移比對與同步)

* **目標主機**：`servers`（正向疊加模型，專屬標準作業系統伺服器群）
* **核心機制**：
  - 採集線上節點的即時套件事實，並透過 [`scripts/sync_host_package_vars.py`](../../../../ansible/scripts/sync_host_package_vars.py) 比對 `host_vars/<hostname>.yml`。
  - 計算出「線上新增 `+`」與「線上缺少 `-`」之漂移項目。
  - 若無漂移，顯示 `✅ [hostname] 線上主機現況與 Repo IaC 完全一致，無漂移。`。
  - 若檢測到漂移，格式化輸出警告報表，並互動暫停詢問：
    `是否將 ansible 對應 host 的 package list (host_vars/<hostname>.yml) 更新成現狀？ (輸入 'yes' 確認同步，其餘任意鍵略過):`
  - 確認後原子化更新 `host_vars/<hostname>.yml` 與 `openlab-configs/node-information/packages_<hostname>.json`。
* **執行命令**：
  ```bash
  # 互動模式 (手動確認是否同步)
  ansible-playbook -i inventory/hosts.yml playbooks/sync-package-inventory.yml

  # 非互動自動同步模式
  ansible-playbook -i inventory/hosts.yml playbooks/sync-package-inventory.yml -e "auto_sync=true"
  ```
