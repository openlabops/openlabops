# Core Config 集中配置與路徑解析模組 (`lib/core/config.py`)

[`lib/core/config.py`](../../../../tools/lib/core/config.py) 是 OpenLabOps 工具鏈的集中配置加載器與動態路徑解析模組。它遵循 **零依賴 (Zero-Dependency)** 與 **環境解耦 (Environment Decoupling)** 原則，為所有 CLI 工具提供統一的組態查詢介面，消除了程式碼中對本機固定目錄（如 `/home/labadmin/openlab-configs` 或 `/home/labadmin/openlab-secrets`）的硬編碼依賴。

---

## 1. 設計哲學與解耦規範

1. **配置與程式碼嚴格分離**：所有系統路徑、API 端點、倉庫名稱與受控金鑰清單皆收斂於 [`conf/tools.config.json`](../../../../tools/conf/tools.config.json)。
2. **多重優先級路徑解析 (Resolution Priority)**：
   - **最高級**：環境變數覆寫（如 `WORKSPACE_CONFIGS_DIR`、`NODE_INFO_DIR`、`TOOLS_CONFIG`、`GITEA_URL`）。
   - **次高級**：本地同層開發倉庫（Dev Sibling Resolution: `../openlab-configs`、`../openlab-secrets`）。
   - **標準層**：使用者快取目錄（`~/.cache/openlab/`）。
   - **保底層**：組態設定檔與預設值。
3. **零第三方依賴**：100% 使用 Python 3 標準函式庫 (`os`, `json`, `pathlib`)。

---

## 2. API 介面規格

### 2.1 組態加載

```python
def load_config() -> dict
```
- 加載並快取 `conf/tools.config.json` 的字典內容。
- 自動讀取並套用環境變數覆寫：
  - `GITEA_URL` -> `config["gitea"]["url"]`
  - `REPO_OWNER` -> `config["gitea"]["owner"]`
  - `TOKEN_FILE` -> `config["gitea"]["token_file"]`
  - `NETWORK_CONTROLLER_IP` -> `config["network"]["controller_ip"]`

### 2.2 捷徑查詢函式

| 函式 | 回傳型態 | 預設值 / 說明 |
| :--- | :--- | :--- |
| `get_gitea_url()` | `str` | `http://gitea.lab` (私有 Gitea 服務位址，對齊 `git_platform.host`) |
| `get_repo_owner()` | `str` | `OpenLabOps` (Gitea 組織名稱，對齊 `git_platform.org`) |
| `get_admin_user()` | `str` | `labadmin` / `admin` (系統管理員帳號，對齊 `cluster.admin_user`) |
| `get_ansible_user()` | `str` | `lab` / `ansible` (Ansible 運維主帳號，對齊 `cluster.ansible_user`) |
| `get_cluster_prefix()` | `str` | `openlab` / `openlab` (聯邦倉庫前綴，對齊 `git_platform.repo_prefix`) |
| `get_cluster_name()` | `str` | `OpenLabOps` / `OpenLab` (叢集宣告名稱，對齊 `cluster.name`) |
| `get_repo_name(key)` | `str` | 查詢 Gitea 倉庫名稱（如 `workflows` -> `${prefix}-workflows`） |
| `get_manifest_path()` | `Path` | 取得當前環境之 Tier 2 站點宣告檔路徑 (`conf/*.manifest.yml`) |
| `get_manifest_value(sec, key)` | `str` | 安全提取 Tier 2 Manifest 指定區塊鍵值 (零依賴字串解析) |
| `get_token_file()` | `str` | `/usr/local/bin/openlab/.gitea_token` |
| `get_path(key, default)` | `str` | 查詢通用路徑，自動展開 `~` 波浪符號為使用者家目錄 |
| `get_cache_dir()` | `Path` | 使用者快取目錄（預設 `~/.cache/openlab`，支援 `OPENLAB_CACHE_DIR` 覆寫） |
| `get_node_info_dir()` | `Path` | 自動定位節點事實目錄（環境變數 > 本地倉庫 > 內部快取） |
| `get_managed_keys()` | `list` | 取得受控金鑰清冊 (`id_user.key`, `ansible.key`, `ansible.key`, `git.key`) |
| `get_endpoint_hosts()` | `list` | 取得合法個人端點清冊 (`laptop`, `workstation`) |

---

## 3. 使用範例

```python
from core.config import get_path, get_node_info_dir, get_managed_keys

# 1. 取得受控 SSH 目錄
ssh_dir = get_path("ssh_dir", "~/.ssh")

# 2. 獲取 node-information 目錄（支援便攜開發模式與獨立快取模式）
node_dir = get_node_info_dir()

# 3. 遍歷受控金鑰清單
for key in get_managed_keys():
    print(f"Key: {key['name']} ({key['type']}) - {key['desc']}")
```
