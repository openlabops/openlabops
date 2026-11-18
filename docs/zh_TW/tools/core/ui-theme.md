# UI Theme 核心庫模組說明文件

[`lib/core/ui_theme.py`](../../../../tools/lib/core/ui_theme.py) 負責終端機高質感 ANSI 色彩渲染、標題框、資訊鍵值對 (`Key-Value`) 及分隔線繪製。

---

## 核心 API 清單

| 功能 API | Python 介面 (`core.ui_theme`) | 說明 |
| :--- | :--- | :--- |
| **主標題抬頭** | `ui_header("標題文字")` | 輸出帶雙框線之置中主題抬頭 |
| **一般資訊** | `ui_info("訊息")` | 藍色 `[INFO]` 提示 |
| **成功提示** | `ui_success("訊息")` | 綠色 `[SUCCESS]` 提示 |
| **警告提示** | `ui_warn("訊息")` | 黃色 `[WARN]` 提示 |
| **錯誤提示** | `ui_error("訊息")` | 紅色 `[ERROR]` 提示 |
| **鍵值顯示** | `ui_kv("Key", "Value")` | 對齊格式化鍵值輸出 |
| **區隔線** | `ui_divider()` | 輸出單線終端區隔線 |

---

## 程式碼解說與用法範例

引用方式：
```python
from core.ui_theme import ui_header, ui_info, ui_kv, ui_divider, ui_success

ui_header("OpenLabOps Management Console")
ui_info("正在讀取設定檔...")
ui_kv("狀態", "正常")
ui_divider()
ui_success("初始化完成！")
```

