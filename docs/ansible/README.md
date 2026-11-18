# OpenLabOps Ansible 自動化維運手冊導覽 (docs/ansible/)
> 本目錄集中管理 `openlab-ansible` 儲存庫的架構規範、解耦角色規格、20 大 Playbook 矩陣與審計腳本說明。

---

## 1. 結構與導覽地圖 (Directory Structure)

```text
docs/ansible/
├── README.md                                    # 本導覽手冊
├── inventory.md                                 # 多維自動預分類拓撲 (distros, subnets, capabilities, appliances)
├── roles-modularization-spec.md                 # 7 大解耦角色規格 (baseline, users, dotfiles, tools, docker, ssh, gateway)
├── custom-package-facts.md                      # custom_package_facts 模組規格與使用指南
│
├── playbooks/                                   # 20 大 Ansible 標準維運劇本詳解
│   ├── playbooks-overview.md                    # 20 劇本矩陣、調用角色與執行 Tags 總覽
│   ├── node-provisioning.md                     # 三階段 7/24 伺服器初次納管與系統基線建置
│   ├── package-management.md                    # 套件採集、升級探測與 IaC 同步劇本說明
│   ├── dotfiles-deployment.md                   # Shell 與 Neovim NvChad 跨平台部署說明
│   └── endpoint-bootstrap.md                    # 外部端點 ansible-pull 自舉架構
│
└── scripts/                                     # 遠端審計與本地輔助腳本
    ├── sync-host-package-vars.md                # sync_host_package_vars.py IaC 雙向同步工具
    └── audit-nodes.md                           # 跨平台 (Linux/BSD/Virtualization) 節點即時審計腳本
```

---

## 2. 核心規範與快速跳轉 (Direct Links)

* **積木化角色規範**：[7 大解耦角色規格書](roles-modularization-spec.md)
* **庫存與預分類拓撲**：[Inventory 多維預分類與設備隔離規範](inventory.md)
* **自動化劇本總覽**：[20 大 Playbooks 調度架構矩陣](playbooks/playbooks-overview.md)
* **系統初建與基線**：[新節點佈署劇本 (Node Provisioning)](playbooks/node-provisioning.md)
* **環境與組態分發**：[個人化 Dotfiles 部署劇本](playbooks/dotfiles-deployment.md)
* **套件與 IaC 狀態**：[自訂套件事實模組](custom-package-facts.md) ｜ [套件管理劇本手冊](playbooks/package-management.md)
