#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Core Library: Modern Curses TUI Engine
Zero External Dependencies: 100% Python Standard Library [INV-01].
Provides a dual-column, responsive, Vim-navigable full-terminal interface
with automatic headless fallback for scripts and CI/CD pipelines.
"""

import os
import sys
import time
import curses
import traceback
import unicodedata
from typing import List, Dict, Callable, Any, Optional

from .ui_theme import char_width, str_width


def slice_to_width(s: str, max_w: int) -> str:
    """依終端顯示寬度精確截斷字串，絕不超出 max_w 欄位。"""
    cur_w = 0
    res = []
    for c in s:
        cw = char_width(c)
        if cur_w + cw > max_w:
            break
        res.append(c)
        cur_w += cw
    return "".join(res)


def _safe_addstr(stdscr, y: int, x: int, text: str, attr: int = 0):
    """
    安全向 Curses 視窗輸出字串：
    1. 驗證座標邊界，防止 IndexError。
    2. 針對終端右下角 (max_y - 1, max_x - 1) 保留安全餘量，杜絕 addwstr() ERR 崩潰。
    3. 自動根據剩餘寬度進行 CJK 雙寬度截斷。
    4. 全域捕捉 curses.error 異常。
    """
    try:
        max_y, max_x = stdscr.getmaxyx()
        if y < 0 or y >= max_y or x < 0 or x >= max_x:
            return
        avail = max_x - x
        # Curses 致命規範：在最後一行的最後一格寫入字元會導致游標無法後移而觸發 ERR
        if y == max_y - 1:
            avail = max(0, avail - 1)
        if avail <= 0:
            return
        disp_text = slice_to_width(text, avail)
        if disp_text:
            stdscr.addstr(y, x, disp_text, attr)
    except Exception:
        pass


def is_tui_supported() -> bool:
    """Check if the environment supports an interactive curses TUI."""
    if not sys.stdin.isatty():
        return False
    if any(arg in sys.argv for arg in ("--no-tui", "--plain", "--batch", "-b", "--non-interactive")):
        return False
    term = os.environ.get("TERM", "")
    if term in ("dumb", "unknown", ""):
        return False
    return True


class CursesTUI:
    """
    Zero-dependency modern TUI manager using Python standard library `curses`.
    Supports dual-column layout (Categories on left, Actions & Details on right),
    status bar, responsive resizing, and clean suspension for child subcommands.
    """

    def __init__(self, title: str = "OpenLabOps Homelab Control Suite", subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        self.categories: List[Dict[str, Any]] = []
        self.selected_cat: int = 0
        self.selected_item: int = 0
        self.focus_left: bool = True
        self.status_msg: str = "就緒 (Ready)"
        self.last_status_time: float = time.time()

    def add_category(self, name: str, desc: str, items: List[Dict[str, Any]]):
        """Register a category with an array of action items."""
        self.categories.append({
            "name": name,
            "desc": desc,
            "items": items
        })

    def init_colors(self):
        """Initialize color pairs with default terminal background fallback."""
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except Exception:
            bg = curses.COLOR_BLACK

        # Pair mappings (嚴格對齊 docs/tools/core/ui-theme.md 與 ui_theme.py 規範，杜絕反光眩光)
        curses.init_pair(1, curses.COLOR_WHITE, bg)                 # Default text (White on native bg)
        curses.init_pair(2, curses.COLOR_CYAN, bg)                  # Header / Frames (C_CYAN)
        curses.init_pair(3, curses.COLOR_GREEN, bg)                 # Active cursor item (C_GREEN on native bg, 杜絕反光)
        curses.init_pair(4, curses.COLOR_GREEN, bg)                 # Success / Badges (C_GREEN)
        curses.init_pair(5, curses.COLOR_YELLOW, bg)                # Warning / Highlights (C_YELLOW)
        curses.init_pair(6, curses.COLOR_RED, bg)                   # Error / Alerts (C_RED)
        curses.init_pair(7, curses.COLOR_CYAN, bg)                  # Secondary / Muted (Cyan Dim, 替代暗淡難辨之深藍)
        curses.init_pair(8, curses.COLOR_CYAN, bg)                  # Active category cursor (C_CYAN on native bg)

    def set_status(self, msg: str):
        self.status_msg = msg
        self.last_status_time = time.time()

    def draw(self, stdscr):
        max_y, max_x = stdscr.getmaxyx()

        # Minimum dimension guard (80x24 standard)
        if max_y < 22 or max_x < 78:
            stdscr.erase()
            warn = f"終端視窗尺寸需至少 78x22 (目前: {max_x}x{max_y})"
            _safe_addstr(stdscr, 0, 0, warn)
            stdscr.refresh()
            return

        stdscr.erase()

        # 1. Header Bar
        now_str = time.strftime("%H:%M:%S")
        header_l = f" 🥝 {self.title} "
        if self.subtitle:
            header_l += f"({self.subtitle}) "

        _safe_addstr(stdscr, 0, 2, header_l, curses.color_pair(2) | curses.A_BOLD)
        time_badge = f"[{now_str}] "
        _safe_addstr(stdscr, 0, max_x - len(time_badge) - 2, time_badge, curses.color_pair(2) | curses.A_BOLD)

        # 2. Main Layout Coordinates
        left_w = min(28, max_x // 3)
        top_y = 1
        bottom_y = max_y - 4

        # Draw Frame Borders
        border_attr = curses.color_pair(2) | curses.A_DIM
        for y in range(top_y + 1, bottom_y):
            _safe_addstr(stdscr, y, 0, "│", border_attr)
            _safe_addstr(stdscr, y, left_w, "│", border_attr)
            _safe_addstr(stdscr, y, max_x - 1, "│", border_attr)

        # Top border
        top_border = "╭" + "─" * max(0, left_w - 1) + "┬" + "─" * max(0, max_x - left_w - 2) + "╮"
        _safe_addstr(stdscr, top_y, 0, top_border, border_attr)
        # Middle divider
        mid_border = "├" + "─" * max(0, left_w - 1) + "┴" + "─" * max(0, max_x - left_w - 2) + "┤"
        _safe_addstr(stdscr, bottom_y, 0, mid_border, border_attr)
        # Bottom status bar border
        bot_border = "╰" + "─" * max(0, max_x - 2) + "╯"
        _safe_addstr(stdscr, max_y - 1, 0, bot_border, border_attr)

        # 3. Draw Left Pane (Categories)
        cat_header = " 導航分類 (Categories) "
        _safe_addstr(stdscr, top_y, 2, cat_header, curses.color_pair(2) | curses.A_BOLD)

        for idx, cat in enumerate(self.categories):
            y = top_y + 2 + idx * 2
            if y >= bottom_y:
                break

            cat_label = f"[{idx + 1}] {cat['name']}"
            if str_width(cat_label) > left_w - 4:
                cat_label = slice_to_width(cat_label, left_w - 6) + "…"

            if idx == self.selected_cat:
                if self.focus_left:
                    cursor_text = f" ➜ {cat_label} "
                    _safe_addstr(stdscr, y, 1, cursor_text, curses.color_pair(3) | curses.A_BOLD)
                else:
                    cursor_text = f" ● {cat_label} "
                    _safe_addstr(stdscr, y, 1, cursor_text, curses.color_pair(8) | curses.A_BOLD)
            else:
                _safe_addstr(stdscr, y, 3, cat_label, curses.color_pair(1))

        # 4. Draw Right Pane (Actions & Details)
        right_start_x = left_w + 2
        right_w = max_x - left_w - 4

        curr_cat = self.categories[self.selected_cat] if self.categories else None
        if curr_cat:
            # Category Description
            cat_desc_hdr = f" 【{curr_cat['name']}】 "
            _safe_addstr(stdscr, top_y, right_start_x, cat_desc_hdr, curses.color_pair(2) | curses.A_BOLD)

            if curr_cat.get("desc"):
                desc_text = f"• {curr_cat['desc']}"
                _safe_addstr(stdscr, top_y + 1, right_start_x + 1, desc_text, curses.color_pair(7) | curses.A_DIM)

            items = curr_cat.get("items", [])
            for idx, item in enumerate(items):
                y = top_y + 3 + idx * 2
                if y >= bottom_y:
                    break

                item_title = item.get("name", "未命名動作")
                item_desc = item.get("desc", "")
                shortcut = item.get("shortcut", f"[{idx + 1}]")

                prefix = f" {shortcut} {item_title} "
                if idx == self.selected_item and not self.focus_left:
                    act_text = f" ➜ {prefix}"
                    _safe_addstr(stdscr, y, right_start_x + 1, act_text, curses.color_pair(3) | curses.A_BOLD)
                    if item_desc and y + 1 < bottom_y:
                        desc_t = f"↳ {item_desc}"
                        _safe_addstr(stdscr, y + 1, right_start_x + 6, desc_t, curses.color_pair(5))
                else:
                    _safe_addstr(stdscr, y, right_start_x + 3, prefix, curses.color_pair(1))
                    if item_desc and y + 1 < bottom_y:
                        desc_t = f"↳ {item_desc}"
                        _safe_addstr(stdscr, y + 1, right_start_x + 6, desc_t, curses.color_pair(1) | curses.A_DIM)

        # 5. Status / Log Pane
        status_line = f" 狀態: {self.status_msg}"
        _safe_addstr(stdscr, bottom_y + 1, 2, status_line, curses.color_pair(4) | curses.A_BOLD)

        # 6. Footer Navigation Hints
        hints = " [↑/↓/j/k] 導航  [Tab/h/l] 切換欄位  [Enter] 執行  [1-6] 快捷選取  [r] 刷新  [q] 離開"
        _safe_addstr(stdscr, bottom_y + 2, 2, hints, curses.color_pair(1) | curses.A_DIM)

        stdscr.refresh()

    def execute_action(self, stdscr, action_callable: Callable[[], Any], item_name: str):
        """Suspend curses cleanly, execute interactive command, then restore curses."""
        curses.def_prog_mode()
        curses.endwin()

        print("\n" + "=" * 76)
        print(f"  🚀 正在執行: {item_name}")
        print("=" * 76 + "\n")

        try:
            action_callable()
        except KeyboardInterrupt:
            print("\n[!] 使用者已中斷操作。")
        except Exception as e:
            print(f"\n[✖] 執行發生錯誤: {e}")
            traceback.print_exc()
        finally:
            print("\n" + "-" * 76)
            try:
                input("  👉 請按 Enter 鍵返回 TUI 控制台...")
            except (KeyboardInterrupt, EOFError):
                pass
            curses.reset_prog_mode()
            stdscr.refresh()
            self.set_status(f"已完成: {item_name}")

    def run(self, stdscr):
        curses.curs_set(0)
        self.init_colors()
        stdscr.timeout(100) # 100ms non-blocking loop

        while True:
            self.draw(stdscr)
            try:
                ch = stdscr.getch()
            except Exception:
                continue

            if ch == -1:
                continue

            # Quit keys
            if ch in (ord('q'), ord('Q'), 27): # 27 is ESC
                break

            # Refresh
            elif ch in (ord('r'), ord('R')):
                self.set_status("畫面與快取已刷新")
                continue

            # Direct number jump (1 to 9)
            elif ord('1') <= ch <= ord('9'):
                idx = ch - ord('1')
                if idx < len(self.categories):
                    self.selected_cat = idx
                    self.selected_item = 0
                    self.focus_left = False
                    self.set_status(f"切換至: {self.categories[idx]['name']}")
                continue

            # Switch pane focus: Tab, Left/Right, h/l
            elif ch in (ord('\t'), curses.KEY_BTAB):
                self.focus_left = not self.focus_left
                self.set_status(f"焦點切換至: {'左側分類列' if self.focus_left else '右側操作清單'}")

            elif ch in (curses.KEY_LEFT, ord('h')):
                self.focus_left = True

            elif ch in (curses.KEY_RIGHT, ord('l')):
                self.focus_left = False

            # Up navigation
            elif ch in (curses.KEY_UP, ord('k')):
                if self.focus_left:
                    self.selected_cat = (self.selected_cat - 1) % len(self.categories)
                    self.selected_item = 0
                else:
                    curr_items = self.categories[self.selected_cat].get("items", [])
                    if curr_items:
                        self.selected_item = (self.selected_item - 1) % len(curr_items)

            # Down navigation
            elif ch in (curses.KEY_DOWN, ord('j')):
                if self.focus_left:
                    self.selected_cat = (self.selected_cat + 1) % len(self.categories)
                    self.selected_item = 0
                else:
                    curr_items = self.categories[self.selected_cat].get("items", [])
                    if curr_items:
                        self.selected_item = (self.selected_item + 1) % len(curr_items)

            # Execute: Enter
            elif ch in (ord('\n'), ord('\r'), curses.KEY_ENTER):
                if self.focus_left:
                    # Switch focus to right pane
                    self.focus_left = False
                else:
                    curr_items = self.categories[self.selected_cat].get("items", [])
                    if curr_items and 0 <= self.selected_item < len(curr_items):
                        target_item = curr_items[self.selected_item]
                        act = target_item.get("action")
                        if callable(act):
                            self.execute_action(stdscr, act, target_item.get("name", "Action"))


def run_tui(tui: CursesTUI):
    """Convenience launcher for CursesTUI wrapped in curses.wrapper."""
    curses.wrapper(tui.run)

