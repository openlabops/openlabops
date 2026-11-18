# OpenLabOps Tools 工具鏈導覽手冊 (docs/tools/)

本目錄集中維護 OpenLabOps Operations Engine 所有 Python 3 純標準庫維運命令列工具、核心函式庫與架構規範。

---

## 結構與導覽地圖 (Directory Structure)

```text
docs/tools/
├── README.md                            # 本導覽地圖手冊
├── todo.md                              # 專案待辦事項與演進路線圖
│
├── 規格與架構手冊 (Specifications)
│   ├── curses-tui-spec.md              # Curses 雙欄自適應 TUI 互動介面規範書
│   ├── installation-spec.md            # 工具鏈零依賴安裝與 /usr/local/bin 符號連結規範
│   ├── ssh-tools-integration.md        # SSH 金鑰管理與工具整合規範 (對齊 Secrets SSOT)
│   └── versioning-spec.md              # 工具鏈語意化版本號 (SemVer) 與多層級更新規範
│
├── 核心函式庫手冊 (Core API Libraries)
│   ├── core/config.md                  # 集中設定與路徑解析核心模組
│   ├── core/gitea-api.md               # Gitea REST API 封裝與免密 Token 讀取模組
│   ├── core/live-probe.md              # 活體主機狀態即時探測模組
│   ├── core/render-node-doc.md         # JSON 遙測事實 Markdown 渲染引擎
│   ├── core/ui-menu.md                 # TUI 選單、方向鍵光棒、確認框與 Spinner
│   ├── core/ui-theme.md                # ANSI 終端色彩與樣式函式庫
│   └── core/version.md                 # 核心版本管控模組 (SSOT 查詢、比對與 Gitea 探測)
│
└── 實用運維 CLI / TUI 工具手冊 (Operational Tools)
    ├── lab-tools.md                   # 叢集總控制台手冊 (雙欄自適應 Curses TUI / 序列式選單)
    ├── lab-status.md                  # 叢集全域狀態巡檢、90天金鑰年齡與後門公鑰檢測儀表板
    ├── lab-ssh.md                     # 智慧 SSH 連線選擇器與四階段金鑰輪替工具
    ├── lab-backup.md                  # 宣告式節點組態備份至 GitOps CMDB
    ├── lab-upgrade.md                 # 跨平台多發行版套件更新儀表板
    ├── lab-info.md                    # 節點資訊巡檢、工作區同步與手冊渲染套件
    ├── lab-node.md                    # 節點動態引導、探測與納管工具手冊 (Day-0/Day-2 Node Add)
    ├── lab-setup.md                   # 伺服器初建與全網 IaC 基線更新套件
    ├── rotate-keys.md                  # 單一功能金鑰輪換 CLI 派發工具
    └── endpoint-ssh-tools.md           # 端點專屬 SSH 金鑰生成與 Config 同步工具
```

---

## 核心規格與常用工具導讀 (Direct Links)

- **系統架構與維運矩陣**：參見 [架構規範與設計原則](../architecture/tools-architecture.md)。
- **雙欄 Curses TUI 規格**：參見 [Curses TUI 互動介面規範書](curses-tui-spec.md)。
- **工具鏈版本與更新體系**：參見 [工具鏈版本號管控與自動升級規範](versioning-spec.md)。
- **工具鏈零依賴安裝規範**：參見 [工具鏈安裝與部署規範文件](installation-spec.md)。
- **待辦事項與演進路線圖**：參見 [專案待辦事項與改善追蹤清單](todo.md)。
- **叢集總控制台 (lab-tools)**：參見 [lab-Tools TUI 綜合維運控制台手冊](lab-tools.md)。
- **節點動態納管指令手冊**：參見 [lab-node 節點引導與動態納管指令手冊](lab-node.md)。
- **全網狀態與零信任金鑰稽核**：參見 [lab-status 叢集全域狀態巡檢手冊](lab-status.md)。
