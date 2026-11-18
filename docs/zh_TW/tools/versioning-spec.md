# 工具鏈版本號管控與自動升級規範 (docs/architecture/versioning-spec.md)

本文件定義 `openlab-tools` 工具鏈之單一真相源 (SSOT) 版本號管理規範、語意化版本 (SemVer) 比對邏輯、CLI 統一查詢介面與自動更新升級機制。

---

## 1. 設計哲學與核心原則

1. **單一真相源 (Single Source of Truth, SSOT)**：
   - 倉庫根目錄的 [`VERSION`](../../../tools/VERSION) 檔案為唯一版本真相源。
    - 拒絕在個別腳本中硬編碼版本號；所有 CLI 工具與核心模組均從 SSOT 動態載入。
2. **語意化版本 (Semantic Versioning 2.0.0)**：
   - 遵循 `MAJOR.MINOR.PATCH` 規範：
     - `MAJOR`：架構性重大重構或破壞性變更（例如認證流程變革、金鑰路徑重構）。
     - `MINOR`：新增工具、新增核心模組、功能向後相容擴展（例如新增版本管控系統、新增金鑰同步工具）。
     - `PATCH`：向後相容之 Bug 修復、權限修正、文檔更新。
3. **雙身份同權執行 (Dual labadmin & Root Execution)**：
   - 安裝目錄 `/usr/local/bin/openlab/` 及其子目錄採 `0755` 權限，`VERSION` 等數據檔採 `0644`。
   - `labadmin` 一般使用者與 `root` 系統管理員皆可無障礙執行工具與查詢版本，無權限拒絕阻礙。
4. **零 Clone 遠端版本探測 (Zero-Clone Remote Version Probing)**：
   - 透過 Gitea REST API Raw Endpoint (`/api/v1/repos/OpenLabOps/openlab-tools/raw/VERSION`) 查詢最新版本，無需全量 Git Fetch 或 Clone 即可判斷更新必要性。

---

## 2. 檔案目錄結構與 SSOT 落地

```
 openlab-tools/ (Repository)
 ├── VERSION                            # [SSOT] 倉庫主版本號 (1.0.0)
 ├── bin/                               # [標準 CLI] 無副檔名進入點 (chmod 0755)
 │   ├── lab-tools                     # 支援 -v / --version
 │   ├── lab-setup                     # 支援 -v / --version
 │   ├── lab-ssh                       # 支援 -v / --version
 │   ├── lab-info                      # 支援 -v / --version
 │   ├── lab-backup                    # 支援 -v / --version
 │   ├── sync-openlab-tools           # 支援 -v / -c / -f / -l 版本檢查與部署
 │   ├── sync-ssh-keys                  # 支援 -v / --version
 │   ├── sync-ssh-config                # 支援 -v / --version
 │   └── ...
 └── lib/                               # [Python 模組] 核心模組與底層庫
     ├── core/
     │   └── version.py                 # [Python 核心] 版本查詢、比對與 Gitea 探測庫
     └── ...
```

當工具部署至系統環境時：
```
/usr/local/bin/openlab/
├── VERSION                             # [0644] 系統當前安裝版本真相源 (1.0.0)
├── bin/                                # [0755] 可執行檔目錄 (軟連結目標)
├── lib/                                # [0755] Python 模組庫目錄
└── docs/                               # [0644] 文件目錄
```

---

## 3. 核心模組介面規範 (`core.version`)

### 函數清單與規格

- `get_local_version() -> str`：
  依優先順序檢測：
  1. `/usr/local/bin/openlab/VERSION` (系統安裝目錄)
  2. `../../VERSION` (相對於本庫的開發目錄)
  3. `/home/labadmin/openlab-tools/VERSION` (本機工作區備選)
  若皆無法取得則回退至預設值 `1.0.0`。
- `get_remote_version() -> str`：
  透過 Gitea REST API Token 查詢遠端倉庫最新 `VERSION` 內容。
- `compare_versions(v1: str, v2: str) -> int`：
  依 `(MAJOR, MINOR, PATCH)` 元組進行語意化比對：
  - `1`：`v1 > v2` (v1 較新)
  - `-1`：`v1 < v2` (v2 較新)
  - `0`：版本完全一致
- `print_version(tool_name: str)`：
  輸出標準格式：`{tool_name} v{local_version}`。

---

## 4. CLI 工具整合與用法

所有 CLI 工具一律支援統一的 `-v` / `--version` 旗標：

| 命令 | 查詢範例 | 輸出範例 |
| :--- | :--- | :--- |
| `lab-tools` | `lab-tools -v` | `OpenLabOps Cluster Management Console (lab-tools) v1.0.0` |
| `lab-setup` | `lab-setup -v` | `OpenLabOps Server Setup Suite (lab-setup) v1.0.0` |
| `lab-ssh` | `lab-ssh -v` | `OpenLabOps SSH Suite (lab-ssh) v1.0.0` |
| `lab-info` | `lab-info -v` | `OpenLabOps Node Info Suite (lab-info) v1.0.0` |
| `lab-backup` | `lab-backup -v` | `OpenLabOps Backup Suite (lab-backup) v1.0.0` |
| `sync-ops-tools` / `sync-openlab-tools` | `sync-ops-tools -v` | `OpenLabOps Homelab Tools v1.0.0` |
| `sync-ssh-keys` | `sync-ssh-keys -v` | `OpenLabOps Managed SSH Key Sync Tool v1.0.0` |
| `sync-ssh-config` | `sync-ssh-config -v` | `OpenLabOps Standard SSH Client Config Sync Tool v1.0.0` |
| `generate-host-ssh-key` | `generate-host-ssh-key -v` | `OpenLabOps Endpoint SSH Key Toolchain v1.0.0` |
| `revoke-host-ssh-key` | `revoke-host-ssh-key -v` | `OpenLabOps Endpoint Key Revocation Tool v1.0.0` |

---

## 5. 自動升級與智慧比對 (`sync-ops-tools` / `sync-openlab-tools`)

`sync-ops-tools` (亦可透過相容別名 `sync-openlab-tools` 呼叫) 提供版本驅動之自動升級邏輯：

1. **版本檢查模式 (`--check / -c`)**：
   ```bash
   sync-ops-tools --check
   ```
   僅比對本地安裝版本與 Gitea 遠端最新版本，不下載代碼包亦不覆寫。
2. **自動升級模式 (預設)**：
   ```bash
   sudo sync-ops-tools
   ```
   比對遠端版本：
   - 若本地版本 >= 遠端版本：提示「目前已是最新狀態，無需更新」，跳過重複下載與部署。
   - 若遠端版本 > 本地版本：自動自 Gitea 下載最新 `main.tar.gz` 代碼包、解壓縮、安裝至 `/usr/local/bin/openlab`、同步 `VERSION` 檔案並重建軟連結。
3. **強制更新模式 (`--force / -f`)**：
   ```bash
   sudo sync-ops-tools --force
   ```
   無視版本比對結果，強制從遠端下載並重新安裝覆寫。
4. **本機工作區同步模式 (`--local / -l`)**：
   ```bash
   sudo sync-ops-tools --local
   ```
   直接使用 `/home/labadmin/openlab-tools` 本機工作區之代碼與 `VERSION` 部署至系統目錄，適用於本機開發測試。
