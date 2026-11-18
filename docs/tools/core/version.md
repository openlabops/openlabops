# 核心版本管控模組 (docs/core/version.md)

本文件說明 `openlab-tools` 核心版本管控庫 [`lib/core/version.py`](../../../tools/lib/core/version.py) 之設計與 API 規格。

---

## 1. 模組定位

為了解決不同工具各自分散維護版本號導致的資訊不一致問題，版本管控模組將倉庫根目錄的 [`VERSION`](../../../tools/VERSION) 定義為單一真相源 (SSOT)，並對外提供：
1. 本地當前安裝版本讀取。
2. 遠端 Gitea 最新發布版本探測 (透過 REST API)。
3. 語意化版本比對 (Semantic Versioning 2.0.0)。
4. 統一版本字串輸出與 CLI 旗標整合。

---

## 2. Python 介面 (`core.version`)

### 函數清單

```python
from core.version import (
    get_local_version,
    get_remote_version,
    compare_versions,
    print_version,
)
```

#### `get_local_version() -> str`
- 遍歷候選路徑：
  1. `/usr/local/bin/openlab/VERSION`
  2. `../../VERSION`
  3. `/home/labadmin/openlab-tools/VERSION`
- 回傳版本號字串 (例如 `"1.0.0"`，若皆未找到則回退預設值 `"1.0.0"`)。

#### `get_remote_version() -> str`
- 讀取 `/usr/local/bin/openlab/.gitea_token` 或環境變數中的 Gitea API Token。
- 透過 HTTP GET 向 `http://gitea.lab/api/v1/repos/OpenLabOps/openlab-tools/raw/VERSION` 發送請求。
- 回傳遠端最新版本字串 (若無連線或異常則回傳空字串 `""`)。

#### `compare_versions(v1: str, v2: str) -> int`
- 解析版本字串為三元組 `(major, minor, patch)`。
- 回傳：
  - `1`: `v1 > v2`
  - `-1`: `v1 < v2`
  - `0`: `v1 == v2`

#### `print_version(tool_name: str = "OpenLabOps Homelab Tools")`
- 印出格式：`{tool_name} v{get_local_version()}`。

