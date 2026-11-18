# 工具鏈安裝與部署規範文件 (docs/architecture/installation-spec.md)

本文件定義 `openlab-tools` 如何標準化安裝至系統目錄 `/usr/local/bin/openlab/`，並規範軟連結、執行權限與 Gitea Token 之安全管理。

---

## 1. 安裝設計哲學與原則

1. **整合單一目錄落地 (Unified System Directory)**：
   - 工具鏈代碼庫與本地設定檔統一收斂於 `/usr/local/bin/openlab/`。
   - 所有通用指令軟連結建立於 `/usr/local/bin/`，直接加入系統 `$PATH`。
2. **極簡本機依賴 (Minimal Edge Footprint)**：
   - 本機安裝後僅負責三件事：
     1. 生成帶密碼保護之端點 SSH 金鑰對（私鑰永不離開本機）。
     2. 讀取標準免密 Token (`/usr/local/bin/openlab/.gitea_token`)。
     3. 呼叫 Gitea REST API 發送 Dispatch 請求。
   - 後續所有跨主機維運全交由 Gitea Actions 透過 Playbook 執行。
3. **免密 Token 與 RBAC 安全隔離**：
   - 終端全面採用模式 `0600` 之明文 `.gitea_token`，不強制進行密碼加密。
   - 透過專用機器人帳號 `ci-bot` 與 `CI-Dispatchers` 團隊將 Token 權限隔離於 `openlab-workflows`，禁止存取 `openlab-secrets`。

---

## 2. 目錄階層與安裝目標樹 (Filesystem Layout)

```
/usr/local/bin/
├── openlab/                         # [0755] 工具鏈代碼庫與配置落地根目錄
│   ├── .gitea_token                   # [0600] Gitea API Token (模式 0600 免密明文)
│   ├── VERSION                        # [0644] 系統當前安裝版本真相源 (SemVer SSOT: 1.0.0)
│   ├── bin/                           # [0755] 標準 Linux 可執行檔 (無副檔名，shebang python3)
│   │   ├── lab-tools                 # 叢集主維運控制台
│   │   ├── lab-status                # 叢集全域狀態儀表板
│   │   ├── lab-setup                 # 伺服器初建與基線控制台
│   │   ├── lab-ssh                   # 叢集金鑰管理與輪換控制台
│   │   ├── lab-info                  # 節點資訊、工作區同步與渲染
│   │   ├── lab-backup                # 叢集備份與共用組態廣播控制台
│   │   ├── lab-upgrade               # 叢集多節點並行升級與儀表板工具
│   │   ├── sync-ops-tools             # 中性維運工具鏈自更新與系統目錄部署工具
│   │   ├── sync-openlab-tools       # (相容別名軟連結)
│   │   ├── sync-ssh-config            # 標準 ~/.ssh/config 同步工具
│   │   ├── sync-ssh-keys              # 受控 SSH 管理私鑰/公鑰同步工具
│   │   ├── generate-host-ssh-key      # 端點 SSH 金鑰生成 (支援 WSL 自動辨識)
│   │   ├── revoke-host-ssh-key        # 端點 SSH 金鑰全網清除工具
│   │   └── render-node-doc            # 節點資訊 Markdown 渲染引擎
│   ├── lib/                           # [0755] Python 3 模組庫 (全標準庫)
│   │   ├── __pycache__/               # [0755] 預編譯字節碼目錄 (root 生成)
│   │   │   └── *.pyc                  # [0644] AOT 預編譯字節碼快取 (消除執行編譯延遲)
│   │   ├── core/                      # gitea_api.py, ui_theme.py, ui_menu.py, version.py 等
│   │   └── *.py                       # 核心邏輯與輪換派發模組
│   └── (已移除分散 docs/，全域文檔依 [INV-06] 集中於 docs/)
│
├── lab-tools -> openlab/bin/lab-tools
├── lab-status -> openlab/bin/lab-status
├── lab-setup -> openlab/bin/lab-setup
├── lab-ssh -> openlab/bin/lab-ssh
├── lab-info -> openlab/bin/lab-info
├── lab-backup -> openlab/bin/lab-backup
├── lab-upgrade -> openlab/bin/lab-upgrade
├── sync-ops-tools -> openlab/bin/sync-ops-tools
├── sync-openlab-tools -> openlab/bin/sync-openlab-tools
├── sync-ssh-config -> openlab/bin/sync-ssh-config
├── sync-ssh-keys -> openlab/bin/sync-ssh-keys
├── generate-host-ssh-key -> openlab/bin/generate-host-ssh-key
├── revoke-host-ssh-key -> openlab/bin/revoke-host-ssh-key
├── render-node-doc -> openlab/bin/render-node-doc

~/.ssh/
└── sockets/                           # [0700] OpenSSH ControlMaster 連線通道 Socket 落地目錄
```

---

## 3. 安裝步驟規範 (`sync-openlab-tools` / Playbook)

1. **依賴環境檢查**：
   - 確保 Python 3.8+ 就緒。
   - 確保基礎命令列工具就緒：`git`, `curl`, `jq`, `openssl`, `rsync`。
2. **檔案同步至 `/usr/local/bin/openlab/`**：
   - 同步 `bin/`、`lib/`、`docs/` 目錄與 `VERSION` 檔案。
   - 清理廢棄之舊版目錄（如舊版 `script/`、`python/`）。
   - `bin/` 內所有無副檔名 CLI 執行檔與 `lib/` 模組賦予 `0755` 權限，數據檔案賦予 `0644`。
3. **軟連結建立**：
   - 建立 `/usr/local/bin/<cmd>` 指向 `/usr/local/bin/openlab/bin/<cmd>` 之標準軟連結。
4. **Python Bytecode 事前編譯 (AOT Compilation)**：
   - 安裝程序於 root 權限下調用 `python3 -m compileall -f -q /usr/local/bin/openlab/lib`。
   - 強制遞迴將產出的 `.pyc` 檔案權限死鎖為 `chmod 0644`。
   - 解決非 root 使用者執行 CLI 時因無寫入權限而無法持久化 `.pyc` 導致每次即時編譯的問題。
5. **OpenSSH 連線通道 Socket 目錄初始化**：
   - 執行者主目錄下自動確保 `~/.ssh/sockets/` 存在。
   - 強制設定目錄權限為 `chmod 0700`，供 `ControlMaster` 存放 IPC Socket。
6. **Token 配置**：
   - 將 `ci-bot` 簽發之受限 Token 放置於 `/usr/local/bin/openlab/.gitea_token`。
   - 強制設定權限為 `chmod 0600`。

---

## 4. 權限與安全邊界清單

| 目標檔案 / 目錄 | 建議權限 | 擁有者:群組 | 安全說明 |
| :--- | :---: | :--- | :--- |
| `/usr/local/bin/openlab/` | `0755` | `root:root` | 工具鏈代碼庫落地根目錄 |
| `/usr/local/bin/openlab/.gitea_token` | `0600` | 執行者帳號 | 免密明文 Token，嚴禁其他帳號讀取 |
| `/usr/local/bin/openlab/lib/**/__pycache__/*.pyc` | `0644` | `root:root` | AOT 預編譯字節碼快取，全域唯讀 |
| `/usr/local/bin/lab-*` | `0755` | `root:root` | 系統通用命令列工具軟連結 |
| `~/.ssh/sockets/` | `0700` | 執行者帳號 | OpenSSH 連線多工 ControlPath 通道目錄 |
| `~/.ssh/$hostname.key` | `0600` | 執行者帳號 | 本地端點私鑰，強制密碼保護，嚴禁上傳託管 |
