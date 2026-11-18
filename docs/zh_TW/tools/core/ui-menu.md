# UI Menu 核心庫模組說明文件

[`lib/core/ui_menu.py`](../../../../tools/lib/core/ui_menu.py) 負責處理終端互動選單、方向鍵光棒選取、數字編號輸入、Yes/No 確認詢問框與動態多線程 Spinner 載入進度提示。

---

## 核心互動組件清單

| 組件名稱 | 介面語法 | 說明與特點 |
| :--- | :--- | :--- |
| **Yes/No 確認對話框** | `ui_confirm("提示", default="y")` | 支援 Enter 快速接受預設值 (預設 N/y)，色彩高亮 |
| **單選互動選單** | `ui_select("標題", options)` | 雙模支援：方向鍵 (↑/↓) 光棒移動或直接輸入數字編號 |
| **動態載入 Spinner** | `with ui_spinner("訊息"):` | Python 上下文管理器 (`contextmanager`)，背景守護線程流暢動畫 |

---

## 程式碼解說與用法

### 1. Yes/No 確認框 (`ui_confirm`)

```python
from core.ui_menu import ui_confirm

if ui_confirm("確定要重新啟動服務嗎？", default="y"):
    print("執行重啟")
```

---

### 2. 單選選單 (`ui_select`)

支援方向鍵上下導航高亮光棒，或直接輸入選項數字：

```python
from core.ui_menu import ui_select

options = ["部署 Compose", "備份資料庫", "離開"]
choice_idx, choice_val = ui_select("請選擇任務:", options)
print(f"您選擇了第 {choice_idx} 項: {choice_val}")
```

---

### 3. 動態進度 Spinner (`ui_spinner`)

採用 Python `with` 語法上下文管理器，多線程繪製旋轉動畫：

```python
import time
from core.ui_menu import ui_spinner

with ui_spinner("正在同步伺服器中..."):
    time.sleep(3)
```

