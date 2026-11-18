# custom_package_facts 模組說明文件 (Ansible Custom Module Specification)

## 1. 模組簡介
[`library/custom_package_facts.py`](../../ansible/library/custom_package_facts.py) 是為 OpenLabOps Homelab 定製開發的 Ansible 原生套件事實採集模組。該模組繼承並優化了 Ansible 官方 `package_facts` 架構，旨在解決官方模組無法精確區分「主動安裝 vs 純相依套件」、「系統基底 vs 應用程式」，以及無法自動檢測「Upstream 可用更新」等痛點。

---

## 2. 核心功能與跨平台支援

| 作業系統 / 發行版 | 套件管理器 | 主動安裝識別機制 (`install_reason`) | Upstream 升級檢測命令 (`check_upgrades`) | AUR / 第三方庫支援 |
| :--- | :--- | :--- | :--- | :--- |
| **Arch Linux** | `pacman` + `yay` | `pacman -Qi` 解析 `Install Reason: Explicit` | `yay -Qu` (或 `checkupdates`) | 整合 `yay -Qmq`，標記 `source: yay, repo: aur` |
| **BSD** | `pkg` | `pkg query %a` 解析標記 (0=Explicit, 1=Auto) | `pkg upgrade -n` 乾跑比對 | 標記 `source: pkg`，過濾 Vital 核心套件 |
| **Photon OS** | `tdnf` | 逆向解析 `tdnf history` 使用者主動交易 | `tdnf check-update -q` (解析 carriage return) | 標記 `source: tdnf`，過濾 base 核心 |
| **Oracle Linux / RHEL** | `dnf` | 解析 `dnf history list/info` 使用者安裝記錄 | `dnf check-update -q` (捕獲 exit code 100) | 標記 `source: dnf`，過濾 base/kernel 核心 |

---

## 3. 參數說明 (Module Arguments)

| 參數名稱 | 類型 | 預設值 | 說明 |
| :--- | :---: | :---: | :--- |
| `manager` | list | `['auto']` | 指定要查詢的套件管理器清單（可選 `pacman`, `yay`, `pkg`, `tdnf`, `dnf`, `rpm`） |
| `strategy` | str | `'first'` | 查詢策略，可選 `first` (命中首個可用管理器即停) 或 `all` (全量掃描) |
| `filter_dependencies`| bool | `false` | 為 `true` 時，僅傳回主動安裝套件 (`automatic: false`)，過濾純依賴庫 |
| `filter_system` | bool | `false` | 為 `true` 時，過濾系統核心與基底套件 (`system: false`) |
| `check_upgrades` | bool | `false` | 為 `true` 時，自動探測 upstream 是否有可升級的新版套件清單 |

---

## 4. 返回 Facts 結構 (Returned Ansible Facts)

```yaml
ansible_facts:
  packages:                       # 符合過濾條件之套件字典 (依名稱為鍵)
    git:
      - name: "git"
        version: "2.53.0-2.ph5"
        arch: "x86_64"
        category: "System Environment/Programming"
        description: "Fast distributed version control system"
        automatic: false          # 非純相依
        install_reason: "explicit"
        system: false             # 非系統基底
        source: "tdnf"
  explicit_packages:              # 平鋪之主動安裝套件清單 (方便 Jinja2 迭代與比對)
    - name: "git"
      version: "2.53.0-2.ph5"
      ...
  explicit_packages_count: 10     # 主動安裝套件總數
  package_manager_detected: "tdnf" # 偵測到之主要管理器
  upgradeable_packages:           # 可升級套件清單 (check_upgrades=true 時回傳)
    - name: "brave-bin"
      current_version: "1:1.97.57-1"
      new_version: "1:1.97.59-1"
      source: "yay"
      repo: "aur"
  upgradeable_packages_count: 1   # 可升級套件總數
```

---

## 5. Playbook 調用範例

```yaml
- name: 採集線上節點非相依非系統套件並檢查升級
  custom_package_facts:
    filter_dependencies: true
    filter_system: true
    check_upgrades: true
  register: pkg_res
```
