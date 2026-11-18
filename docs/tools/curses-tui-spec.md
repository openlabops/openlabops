# OpenLabOps Tools Curses TUI 互動介面與美化方案規格書

本規格書定義在 **100% Python 3 標準函式庫（Zero External Dependencies / 免 pip 安裝）** 的原則下，如何利用內建 `curses` 模組現代化 `lab-tools` 主程式及各次級工具之多層次互動終端介面（TUI）。

---

## 1. 架構目標與核心價值

### 1.1 現有介面痛點
目前 `lab-tools`、`lab-info`、`lab-ssh` 採用傳統的序列式標準輸出與文字提示輸入（如 `1) ... 2) ... 請輸入選項: `）：
- 無法透過方向鍵（`↑`/`↓`）或 Vim 鍵（`j`/`k`）流暢選取。
- 選單刷新時容易滾動洗版，缺乏視窗固定與即時預覽區域。
- 難以呈現多層次階層關係（例如：左側類別導航、右側即時狀態、下方操作紀錄）。

### 1.2 為什麼選擇 Python 原生 `curses`？
1. **零第三方依賴 (Zero Dependencies)**：Python 原生標準函式庫自帶，任何 Linux（Arch, Debian, PhotonOS, Alpine）、macOS 與 WSL 終端機均預載可用，免除 `pip install` 任何套件。
2. **極致輕量與低延遲**：直接對接 Terminfo 與虛擬終端跳脫序列，即使在延遲較高的遠端 SSH 環境中亦能保持 60 FPS 流暢反饋。
3. **終端通用相容性**：無論是 Linux Console、VSCode / IDE Terminal、WSL、或是 tmux / screen，均能完美適配。

---

## 2. 多層次互動架構設計 (Multi-Level Architecture)

```
+----------------------------------------------------------------------------------+
|  🥝 OpenLabOps Homelab Control Suite v1.0.0       [Gitea: ● 就緒]   10:35:12     |
+----------------------------------------------------------------------------------+
|  導航分類 (Categories)     |  操作項目與即時預覽 (Details & Actions)               |
|                           |                                                      |
|  > [1] 📊 叢集即時狀態     |  ╭── 節點狀態摘要 (Node Summary) ──────────────────╮ |
|    [2] 🖥️  伺服器巡檢與手冊 |  │ srv-node1     Arch Linux         47.9%  ● 正常  │ |
|    [3] 🔑 SSH 金鑰生命週期 |  │ Base          VMware Photon OS   39.0%  ● 正常  │ |
|    [4] ⚙️  配置與套件同步   |  │ Gateway       Linux 6.6       12.1%  ● 正常  │ |
|    [5] 💾 備份與災難復原   |  │ Network         Network (1SW, 3AP)   32 clients     │ |
|    [6] 🛠️  工具鏈自檢與更新 |  ╰──────────────────────────────────────────────────╯ |
|                           |  [Enter] 檢視完整 lab-status   [d] 查看硬體細節     |
+----------------------------------------------------------------------------------+
|  即時日誌與操作反饋 (Console Output)                                              |
|  [INFO] 正在連線至 Gitea API 探測遠端版本... (最新: v1.0.0)                      |
+----------------------------------------------------------------------------------+
|  [↑/↓/j/k] 導航  [Enter] 選取  [Tab] 切換視窗  [r] 刷新  [?] 說明  [q] 離開        |
+----------------------------------------------------------------------------------+
```

### 2.1 三級層次劃分
1. **Level 1: 頂層分類與狀態欄 (Global Header & Category Bar)**
   - 頂部狀態列展示：工具名稱、當前版本、Gitea 認證狀態與系統時間。
   - 左側選單列分類：
     - `📊 叢集狀態 (Cluster Status)`：對接 `lab-status`。
     - `🖥️ 節點手冊 (Node Info & Docs)`：對接 `lab-info` 與 `render-node-doc`。
     - `🔑 SSH 管理 (SSH Key Lifecycle)`：對接 `lab-ssh`、`sync-ssh-keys`、`rotate-*-keys`。
     - `⚙️ 配置同步 (IaC & Packages)`：對接 `sync-package-inventory`、`pull-docker-compose`。
     - `💾 災難復原 (Backup & DR)`：對接 `lab-backup`。
     - `🛠️ 系統維護 (Tools Maintenance)`：對接 `sync-openlab-tools`、`lab-setup`。

2. **Level 2: 子系統互動面板 (Interactive Subsystem Panel)**
   - 右側工作區隨左側選取動態切換：
     - **主機選取器 (Host Selector)**：清單列出 12 台節點，支援輸入關鍵字即時過濾（Fuzzy Filter），選取後可一鍵觸發 SSH 或巡檢。
     - **操作項目清單 (Action List)**：清楚列出各工具之子功能（如更新手冊、導出 JSON、旋轉金鑰）。

3. **Level 3: 底部串流主控台 (Live Streaming Console)**
   - 保留底部 4~6 行作為背景任務執行日誌輸出窗口，當執行 Ansible 或 Git 命令時，輸出即時串流顯示，無需跳出全螢幕 TUI。

---

## 3. 視覺美學與調色盤規範 (Design Aesthetic Tokens)

### 3.1 終端色彩配置 (Color Pairs)
在 `curses.has_colors()` 基礎上，嚴格對齊 [`docs/tools/core/ui-theme.md`](core/ui-theme.md) 與 `core.ui_theme` 之設計調色盤，杜絕刺眼的反白/反光背景區塊，改採純淨深色高對比字色：

| 色對編號 | 前景色 | 背景色 | 用途 |
| :--- | :--- | :--- | :--- |
| `PAIR_DEFAULT` | 白色 (`COLOR_WHITE`) | 預設底色 (`-1` / Terminal Default) | 一般文字、邊框與說明 |
| `PAIR_HEADER` | 青藍色 (`COLOR_CYAN` + Bold) | 預設底色 | 標題列、麵包屑與卡片頭部 (對齊 `C_CYAN` + `C_BOLD`) |
| `PAIR_ACTIVE` | 翠綠色 (`COLOR_GREEN` + Bold) | 預設底色 | 游標目前選取項目（對齊 `ui_menu.py` 箭頭 `➜` 與綠色粗體，無反光眩光） |
| `PAIR_SUCCESS` | 綠色 (`COLOR_GREEN`) | 預設底色 | 健康狀態徽章（`● 正常`、`✔ ALIGNED`，對齊 `C_GREEN`） |
| `PAIR_WARNING` | 琥珀黃 (`COLOR_YELLOW`) | 預設底色 | 注意提示、待更新警報（`▲ UPDATE`，對齊 `C_YELLOW`） |
| `PAIR_ERROR` | 玫瑰紅 (`COLOR_RED` + Bold) | 預設底色 | 連線失敗、斷鏈或安全性警報 (對齊 `C_RED`) |
| `PAIR_MUTED` | 柔和白/青 (`COLOR_WHITE` / `COLOR_CYAN` + Dim) | 預設底色 | 輔助說明文字、次級邊框、時間戳 (對齊 `C_DIM`) |
| `PAIR_ACTIVE_CAT` | 青藍色 (`COLOR_CYAN` + Bold) | 預設底色 | 導航分類焦點項目（`●` 標記，對齊 `C_CYAN` + `C_BOLD`） |

### 3.2 幾何邊框與圖形元素
- **方塊邊框**：使用 Unicode 圓角字元 `╭─╮`、`│ │`、`╰─╯` 或標準 `curses.ACS_*` 字元（自動在不支持 UTF-8 的虛擬終端降級為 ASCII `+-|`）。
- **進度指示器**：Unicode 方塊 `█`、`▓`、`▒`、`░` 呈現容量與百分比。
- **徽章與圖示**：`●` (狀態點)、`✔` (成功)、`✖` (異常)、`▲` (警告)、`➜` (當前游標)。

---

## 4. 關鍵技術架構與容錯機制

### 4.1 視窗自適應縮放 (Responsive Resizing & SIGWINCH)
```python
def handle_resize(stdscr):
    max_y, max_x = stdscr.getmaxyx()
    if max_y < 24 or max_x < 80:
        stdscr.clear()
        stdscr.addstr(0, 0, "視窗尺寸過小，請調整終端機大小至至少 80x24 (目前: %dx%d)" % (max_x, max_y))
        stdscr.refresh()
        return False
    return True
```
- 捕捉 `curses.KEY_RESIZE` 訊號，重新計算 Panels 的大小與佈局，防止終端縮放時拋出例外。

### 4.2 非阻塞事件迴圈 (Non-Blocking Event Loop)
- 設定 `stdscr.nodelay(True)` 或 `stdscr.timeout(200)`（200 毫秒輪詢）：
  - 終端定時刷新時鐘與背景任務狀態。
  - 鍵盤事件即按即應，無須按 Enter 即可切換選項。

### 4.3 無終端與 CI/CD 平滑降級 (Headless Fallback)
```python
if not sys.stdin.isatty() or "--no-tui" in sys.argv:
    # 平滑降級至純文字 CLI / JSON 模式
    run_cli_fallback()
    sys.exit(0)
```
- 當執行於 Gitea Actions Runner、管線（`lab-status | grep`）或無 TTY 環境時，自動繞過 Curses 引擎，保障 CI/CD 腳本相容性。

---

## 5. 核心引擎代碼原型 (`ui_curses.py`)

以下為預定實作於 `openlab-tools/lib/core/ui_curses.py` 之標準庫原型：

```python
#!/usr/bin/env python3
"""
OpenLabOps Modern Curses TUI Engine (Zero External Dependencies)
"""
import curses
import sys
import os

class OpenLabOpsTUI:
    def __init__(self, title="OpenLabOps Homelab Control Suite"):
        self.title = title
        self.selected_cat = 0
        self.selected_item = 0
        self.categories = [
            ("📊 叢集即時狀態", ["完整狀態檢視 (lab-status)", "僅看 SSH 金鑰對齊", "僅看節點與套件"]),
            ("🖥️ 伺服器手冊", ["全網巡檢與手冊轉出 (lab-info -a)", "同步本地工作區 (git pull)", "轉出 Markdown 手冊"]),
            ("🔑 SSH 金鑰管理", ["互動連線至主機 (lab-ssh)", "同步金鑰至目標節點", "建立節點主機金鑰", "輪替全網管理員金鑰"]),
            ("⚙️ 配置與套件", ["同步套件清冊至 IaC", "拉取 Docker Compose 配置", "比對本地與遠端差異"]),
            ("💾 備份與還原", ["執行全網設定打包 (lab-backup)", "檢驗備份完整性", "還原沙箱模擬"]),
            ("🛠️ 工具維護", ["更新工具鏈至本機 (sync --local)", "遠端節點環境初始化 (lab-setup)", "檢驗 CLI 軟連結"]),
        ]

    def init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, -1)              # Default
        curses.init_pair(2, curses.COLOR_CYAN, -1)               # Header
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN) # Active cursor
        curses.init_pair(4, curses.COLOR_GREEN, -1)              # Success
        curses.init_pair(5, curses.COLOR_YELLOW, -1)             # Warning
        curses.init_pair(6, curses.COLOR_RED, -1)                # Error

    def draw(self, stdscr):
        max_y, max_x = stdscr.getmaxyx()
        if max_y < 22 or max_x < 78:
            stdscr.clear()
            stdscr.addstr(0, 0, "終端尺寸需至少 78x22，目前: %dx%d" % (max_x, max_y))
            stdscr.refresh()
            return

        stdscr.erase()

        # 1. 頂部標題列
        header_text = f" 🥝 {self.title} "
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(0, 2, header_text)
        status_text = "[Gitea: ● 就緒] "
        stdscr.addstr(0, max_x - len(status_text) - 2, status_text)
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        # 2. 分割框架 (左欄: 24 寬度, 右欄: 剩餘寬度)
        left_w = 26
        # 左框
        stdscr.attron(curses.A_DIM)
        for y in range(1, max_y - 4):
            stdscr.addstr(y, 0, "│")
            stdscr.addstr(y, left_w, "│")
            stdscr.addstr(y, max_x - 1, "│")
        stdscr.addstr(1, 0, "╭" + "─" * (left_w - 1) + "┬" + "─" * (max_x - left_w - 2) + "╮")
        stdscr.addstr(max_y - 4, 0, "├" + "─" * (left_w - 1) + "┴" + "─" * (max_x - left_w - 2) + "┤")
        stdscr.attroff(curses.A_DIM)

        # 3. 繪製左欄分類
        for idx, (cat_name, _) in enumerate(self.categories):
            y = 3 + idx * 2
            if y >= max_y - 5:
                break
            if idx == self.selected_cat:
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                stdscr.addstr(y, 2, f" {cat_name:<20} ")
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            else:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, 3, cat_name)
                stdscr.attroff(curses.color_pair(1))

        # 4. 繪製右欄子選單項目
        _, items = self.categories[self.selected_cat]
        right_start_x = left_w + 3
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(2, right_start_x, "可執行動作項目 (Actions):")
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

        for idx, item in enumerate(items):
            y = 4 + idx * 2
            if y >= max_y - 5:
                break
            if idx == self.selected_item:
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                stdscr.addstr(y, right_start_x, f" ➜ {item} ")
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            else:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, right_start_x + 3, item)
                stdscr.attroff(curses.color_pair(1))

        # 5. 底部快捷鍵提示列
        footer_y = max_y - 2
        footer_msg = " [↑/↓/j/k] 導航  [Enter] 執行  [Tab] 切換欄位  [r] 刷新  [q] 離開"
        stdscr.attron(curses.color_pair(1) | curses.A_DIM)
        stdscr.addstr(footer_y, 2, footer_msg)
        stdscr.attroff(curses.color_pair(1) | curses.A_DIM)

        stdscr.refresh()

    def run(self, stdscr):
        curses.curs_set(0) # 隱藏光標
        self.init_colors()
        stdscr.timeout(100) # 非阻塞輪詢

        focus_left = True

        while True:
            self.draw(stdscr)
            try:
                ch = stdscr.getch()
            except Exception:
                continue

            if ch == -1:
                continue

            # 退出
            if ch in [ord('q'), ord('Q'), 27]: # 27 is ESC
                break

            # 切換焦點
            elif ch in [ord('\t'), curses.KEY_BTAB]:
                focus_left = not focus_left

            # 導航
            elif ch in [curses.KEY_UP, ord('k')]:
                if focus_left:
                    self.selected_cat = (self.selected_cat - 1) % len(self.categories)
                    self.selected_item = 0
                else:
                    items = self.categories[self.selected_cat][1]
                    self.selected_item = (self.selected_item - 1) % len(items)

            elif ch in [curses.KEY_DOWN, ord('j')]:
                if focus_left:
                    self.selected_cat = (self.selected_cat + 1) % len(self.categories)
                    self.selected_item = 0
                else:
                    items = self.categories[self.selected_cat][1]
                    self.selected_item = (self.selected_item + 1) % len(items)

            elif ch in [ord('\n'), curses.KEY_ENTER]:
                # 執行動作
                break


def start_tui():
    if not sys.stdin.isatty():
        print("非終端環境，略過 TUI。")
        return
    curses.wrapper(lambda stdscr: OpenLabOpsTUI().run(stdscr))


if __name__ == "__main__":
    start_tui()
```

---

## 6. `bsdinstall` 風格對話框引擎 (`engine/bsd_dialog.py`) 排版與防破圖規範

`lab-init` 與 `lab-node` 共用 [`engine/bsd_dialog.py`](../../engine/bsd_dialog.py) 提供的 BSD `bsdinstall` 經典藍底灰框 TUI 介面。為確保多節點資訊或長篇錯誤訊息顯示時絕不發生邊框破圖或文字溢位，必須遵循以下排版規範：

1. **CJK 東亞全形字元寬度計算 (`unicodedata.east_asian_width`)**：
   - 嚴禁直接使用 Python `len()` 計算終端機顯示寬度（每個繁體中文字元佔 2 個終端機 Column，而 `len()` 為 1）。
   - 所有字串截斷（`_slice_to_width`）、補齊（`_pad_to_width`）與置中對齊一律以真實終端機 Column 寬度為準，確保右側邊框 `│` 絕不被擠出。
2. **多行自動換行與捲動檢視 (`_wrap_text` & Scrollable Viewport)**：
   - 當對話框提示文字（`prompt`）、節點清單或錯誤原因包含換行符號 `\n` 或超過對話框內部寬度（`w - 6`）時，必須先透過 `_wrap_text` 按真實顯示寬度拆分為獨立行並逐行繪製於 `x + 3`，嚴禁將含 `\n` 的字串直接傳入 `stdscr.addstr()`（否則 Curses 會跳至螢幕最左側 `x = 0` 覆蓋左邊框）。
   - 當節點資訊或訊息行數超過視窗高度時，自動啟用上下方向鍵（`↑`/`↓`/`PgUp`/`PgDn`）捲動與滾動提示，並動態調整表單與清單起始列座標。
3. **Curses 模式期間禁止原始 `stdout` 輸出與完整 ANSI 清除**：
   - 在 `progress_box` 等 Curses 視窗活動期間，底層回呼函式僅能將訊息傳入 `callback(msg)`，嚴禁同時呼叫 `print()` 直接寫入 `stdout`，並透過正規表示式完整剝除所有 ANSI 色碼（`\x1b\[[0-9;]*[a-zA-Z]`）。
4. **即時密碼輸入對話框 (`password_dialog`)**：
   - 封裝單行隱蔽密碼輸入視窗（以 `*` 遮蔽），專用於運行中任務或 PTY 串流過程中即時攔截並回應用戶端之 Sudo 密碼或私鑰 Passphrase，提供 `<OK>` 與 `<Cancel>` 操作，按 Esc 或 Cancel 立即安全中斷。
5. **多選項核選清單之多行自動縮排排版 (`checklist` Multi-Line Option Layout)**：
   - 勾選清單項目嚴禁將核選框、主標籤（Label）與功能說明（Desc）強制壓縮於單一行內，避免長度超出欄寬而被硬性截斷。
   - 排版統一規範為「標籤在首行、說明自動換行縮排」結構：首行輸出 `  [*] {label}`，說明文字（`desc`）則自動折行（`_wrap_text`）並統一以 6 個半形空格縮排（`      {wrapped_desc}`）展示完畢，後續才呈現下一個核選項目。
   - 選項焦點高亮（`color_pair(3)`）覆蓋該項目的主標籤與所有換行說明列，上下鍵巡覽（`↑`/`↓`/`PgUp`/`PgDn`）依項目區塊整體平滑滾動。

---

## 7. 漸進式替換路徑 (Rollout Plan)

1. **第一階段 (Foundation)**：在 `openlab-tools/lib/core/` 建立 `ui_curses.py` 基礎引擎，封裝標準窗格、色彩配置、按鍵監聽與視窗重繪。
2. **第二階段 (`lab-tools` 主程式切換)**：將 `lab-tools`（無參數執行時）的預設文字選單切換至 Curses TUI，保留 CLI 命令直接執行（如 `lab-tools status` 直接輸出終端而不啟動 TUI）。
3. **第三階段 (`lab-status` 重構與結合)**：
   - 將 `lab-status` 納入此 Curses 架構，讓使用者能在 TUI 中上下巡覽節點、按 Enter 即時查看該節點的 Systemd 服務、Docker 容器與待更新套件清冊，徹底解決純靜態輸出的版面限制。

---

*文檔版本：v1.0.0。建立時間：2026-10-23。*
