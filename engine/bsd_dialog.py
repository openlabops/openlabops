#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps - BSDInstall Curses TUI Dialog Engine
Zero External Dependencies: 100% Python Standard Library (curses) [INV-01].
Provides an authentic bsdinstall / bsddialog text-user interface:
- Deep Blue Screen Canvas with Shadowed Dialog Boxes
- Interactive Forms with Editable Fields and Validation
- Checklists with [X] Space Toggling and Scrolling
- Live Step-by-Step Task Progress Streamers
- Automatic Graceful Fallback for Non-TTY / Dumb / Headless Pipelines
"""

import os
import sys
import time
import curses
import re
import unicodedata
from typing import List, Dict, Any, Optional, Tuple, Callable
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parent.parent / "tools" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from core.ui_theme import strip_ansi, char_width, str_width

# Set low escape sequence delay so ESC is responsive without lagging arrow keys
os.environ.setdefault("ESCDELAY", "25")


def slice_to_width(s: str, max_w: int) -> str:
    """Slice a string so its terminal display width does not exceed max_w."""
    clean = strip_ansi(s)
    cur_w = 0
    res = []
    for c in clean:
        cw = char_width(c)
        if cur_w + cw > max_w:
            break
        res.append(c)
        cur_w += cw
    return "".join(res)


def pad_to_width(s: str, target_w: int) -> str:
    """Pad or slice string to exactly target_w display columns."""
    clean = strip_ansi(s)
    cur_w = str_width(clean)
    if cur_w > target_w:
        return slice_to_width(clean, target_w)
    return clean + (" " * (target_w - cur_w))


def wrap_text(text: str, max_w: int) -> List[str]:
    """
    Wrap text into lines that do not exceed max_w display columns.
    Splits by \\n first, then wraps long lines without breaking CJK words or overflowing.
    """
    raw_lines = strip_ansi(text).split("\n")
    wrapped = []
    for r_line in raw_lines:
        if not r_line:
            wrapped.append("")
            continue
        cur_line = []
        cur_w = 0
        for word in r_line.split(" "):
            w_w = str_width(word)
            if cur_w == 0:
                if w_w <= max_w:
                    cur_line.append(word)
                    cur_w += w_w
                else:
                    for ch in word:
                        cw = char_width(ch)
                        if cur_w + cw > max_w:
                            wrapped.append("".join(cur_line))
                            cur_line = [ch]
                            cur_w = cw
                        else:
                            cur_line.append(ch)
                            cur_w += cw
            elif cur_w + 1 + w_w <= max_w:
                cur_line.append(" " + word)
                cur_w += 1 + w_w
            else:
                wrapped.append("".join(cur_line))
                if w_w <= max_w:
                    cur_line = [word]
                    cur_w = w_w
                else:
                    cur_line = []
                    cur_w = 0
                    for ch in word:
                        cw = char_width(ch)
                        if cur_w + cw > max_w:
                            wrapped.append("".join(cur_line))
                            cur_line = [ch]
                            cur_w = cw
                        else:
                            cur_line.append(ch)
                            cur_w += cw
        if cur_line:
            wrapped.append("".join(cur_line))
    return wrapped


def is_bsd_tui_supported() -> bool:
    """Check if the current terminal environment supports interactive curses TUI."""
    if not sys.stdin.isatty():
        return False
    if any(arg in sys.argv for arg in ("--no-tui", "--plain", "--batch", "--non-interactive", "-q")):
        return False
    term = os.environ.get("TERM", "")
    if term in ("dumb", "unknown", ""):
        return False
    return True


class BSDDialog:
    """
    Zero-dependency authentic bsdinstall-style Dialog Engine.
    Emulates the visual geometry, color scheme, and keyboard navigation
    of bsdinstall(8) / dialog(1).
    """

    def __init__(self, title: str = "OpenLabOps Master Operations Engine", subtitle: str = "Day-0 Initial Setup Wizard"):
        self.title = title
        self.subtitle = subtitle
        self._active_stdscr = None

    def _run_modal(self, run_fn: Callable[[Any], Any]) -> Any:
        """
        Executes a modal curses screen safely. Reuses the active stdscr if already inside
        an existing curses loop (e.g. progress_box streaming), avoiding multiple curses.wrapper
        calls or premature curses termination.
        """
        if self._active_stdscr is not None:
            return run_fn(self._active_stdscr)
        def _wrapper(stdscr):
            self._active_stdscr = stdscr
            try:
                return run_fn(stdscr)
            finally:
                self._active_stdscr = None
        return curses.wrapper(_wrapper)

    def _init_colors(self):
        """Initialize classic BSD installer color palette."""
        curses.start_color()
        # Pair 1: Background & Header (White on Blue)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        # Pair 2: Dialog Box Canvas (Black on Light Gray/White)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        # Pair 3: Active Button / Highlight (White on Blue)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
        # Pair 4: Form Input Field (White on Dark Blue)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
        # Pair 5: Focused Input Field (Yellow/Bold on Dark Blue)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLUE)
        # Pair 6: Dialog Title / Headers (Blue/Bold on Light Gray/White)
        curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_WHITE)
        # Pair 7: Drop Shadow (Black on Blue)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_BLUE)
        # Pair 8: Success Badges (Green on White)
        curses.init_pair(8, curses.COLOR_GREEN, curses.COLOR_WHITE)
        # Pair 9: Warning / Checkbox (Red/Yellow on White)
        curses.init_pair(9, curses.COLOR_RED, curses.COLOR_WHITE)

    def _draw_backdrop(self, stdscr, help_text: str = ""):
        """Draw the solid blue background, top banner, and bottom help line."""
        max_y, max_x = stdscr.getmaxyx()
        stdscr.bkgd(" ", curses.color_pair(1))
        stdscr.erase()

        # Top Banner
        header = f"  {self.title} - {self.subtitle}  "
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        start_x = max(0, (max_x - str_width(header)) // 2)
        try:
            stdscr.addstr(0, start_x, slice_to_width(header, max_x - start_x - 1))
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        # Bottom Status / Navigation Key Help
        footer = help_text or "<Tab> Navigate | <Space> Select | <Enter> Activate | <Esc> Exit"
        stdscr.attron(curses.color_pair(1))
        try:
            stdscr.addstr(max_y - 1, 2, slice_to_width(footer, max_x - 4))
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(1))

    def _draw_box(self, stdscr, y: int, x: int, h: int, w: int, title: str = ""):
        """Draw centered classic dialog box with drop shadow."""
        max_y, max_x = stdscr.getmaxyx()

        # Draw drop shadow (right and bottom)
        for row in range(y + 1, min(max_y, y + h + 1)):
            for col in range(x + 2, min(max_x, x + w + 2)):
                if row == y + h or col >= x + w:
                    try:
                        stdscr.addch(row, col, " ", curses.color_pair(7) | curses.A_DIM)
                    except curses.error:
                        pass

        # Draw dialog box background
        for row in range(y, min(max_y, y + h)):
            try:
                stdscr.addstr(row, x, " " * w, curses.color_pair(2))
            except curses.error:
                pass

        # Draw dialog borders
        box_attr = curses.color_pair(2)
        try:
            # Horizontal lines
            stdscr.addstr(y, x, "┌" + "─" * (w - 2) + "┐", box_attr)
            stdscr.addstr(y + h - 1, x, "└" + "─" * (w - 2) + "┘", box_attr)
            # Vertical lines
            for row in range(y + 1, y + h - 1):
                stdscr.addstr(row, x, "│", box_attr)
                stdscr.addstr(row, x + w - 1, "│", box_attr)
        except curses.error:
            pass

        # Title bar
        if title:
            t_str = f" [ {title} ] "
            t_w = str_width(t_str)
            stdscr.attron(curses.color_pair(6) | curses.A_BOLD)
            start_tx = x + max(2, (w - t_w) // 2)
            try:
                stdscr.addstr(y, start_tx, slice_to_width(t_str, w - 4))
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(6) | curses.A_BOLD)

    def _draw_buttons(self, stdscr, y: int, x: int, w: int, buttons: List[str], active_idx: int):
        """Draw dialog action buttons centered at the bottom of the dialog box."""
        btn_strs = []
        for i, btn in enumerate(buttons):
            if i == active_idx:
                btn_strs.append((f"<  {btn}  >", True))
            else:
                btn_strs.append((f"[  {btn}  ]", False))

        total_btn_len = sum(str_width(b[0]) for b in btn_strs) + (len(btn_strs) - 1) * 3
        start_x = x + max(2, (w - total_btn_len) // 2)

        cur_x = start_x
        for b_str, is_active in btn_strs:
            b_w = str_width(b_str)
            if is_active:
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                try:
                    stdscr.addstr(y, cur_x, b_str)
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            else:
                stdscr.attron(curses.color_pair(2))
                try:
                    stdscr.addstr(y, cur_x, b_str)
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(2))
            cur_x += b_w + 3

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Message Box (msgbox)
    # ──────────────────────────────────────────────────────────────────────────
    def msgbox(self, title: str, text: str, width: int = 70, height: int = 14) -> bool:
        """Display an informational dialog box with an < OK > button and scrolling."""
        def _run(stdscr):
            self._init_colors()
            curses.curs_set(0)
            max_y, max_x = stdscr.getmaxyx()
            w = max(40, min(width, max_x - 4))
            
            wrapped_lines = wrap_text(text, w - 6)
            h = min(max_y - 2, max(height, min(max_y - 2, len(wrapped_lines) + 6)))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            scroll_offset = 0
            visible_rows = max(1, h - 5)

            while True:
                help_msg = "<Enter> to proceed"
                if len(wrapped_lines) > visible_rows:
                    help_msg = "<Up>/<Down>/<PgUp>/<PgDn> Scroll | <Enter> proceed"
                self._draw_backdrop(stdscr, help_msg)
                self._draw_box(stdscr, y, x, h, w, title)

                # Text content
                for i in range(visible_rows):
                    idx = scroll_offset + i
                    if idx >= len(wrapped_lines):
                        break
                    line = wrapped_lines[idx]
                    stdscr.attron(curses.color_pair(2))
                    try:
                        stdscr.addstr(y + 2 + i, x + 3, pad_to_width(line, w - 6))
                    except curses.error:
                        pass
                    stdscr.attroff(curses.color_pair(2))

                # Scroll indicators
                if scroll_offset > 0:
                    try:
                        stdscr.addstr(y + 1, x + w - 5, "▲", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass
                if scroll_offset + visible_rows < len(wrapped_lines):
                    try:
                        stdscr.addstr(y + h - 2, x + w - 5, "▼", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass

                self._draw_buttons(stdscr, y + h - 2, x, w, ["OK"], 0)
                stdscr.refresh()

                ch = stdscr.getch()
                if ch in (10, 13, curses.KEY_ENTER, ord(" "), 27):
                    break
                elif ch in (curses.KEY_UP, ord("k")):
                    if scroll_offset > 0:
                        scroll_offset -= 1
                elif ch in (curses.KEY_DOWN, ord("j")):
                    if scroll_offset + visible_rows < len(wrapped_lines):
                        scroll_offset += 1
                elif ch in (curses.KEY_PPAGE,):
                    scroll_offset = max(0, scroll_offset - visible_rows)
                elif ch in (curses.KEY_NPAGE,):
                    scroll_offset = min(max(0, len(wrapped_lines) - visible_rows), scroll_offset + visible_rows)

            return True

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Yes/No Dialog (yesno)
    # ──────────────────────────────────────────────────────────────────────────
    def yesno(self, title: str, prompt: str, width: int = 70, height: int = 14, default: bool = True) -> bool:
        """Display a confirmation dialog with < Yes > and < No > buttons."""
        def _run(stdscr):
            self._init_colors()
            curses.curs_set(0)
            max_y, max_x = stdscr.getmaxyx()
            w = max(40, min(width, max_x - 4))
            
            wrapped_lines = wrap_text(prompt, w - 6)
            h = min(max_y - 2, max(height, min(max_y - 2, len(wrapped_lines) + 6)))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            btn_idx = 0 if default else 1
            visible_rows = max(1, h - 5)

            while True:
                self._draw_backdrop(stdscr, "<Tab>/<Arrows> Choose | <Enter> Confirm")
                self._draw_box(stdscr, y, x, h, w, title)

                for i in range(visible_rows):
                    if i >= len(wrapped_lines):
                        break
                    line = wrapped_lines[i]
                    stdscr.attron(curses.color_pair(2))
                    try:
                        stdscr.addstr(y + 2 + i, x + 3, pad_to_width(line, w - 6))
                    except curses.error:
                        pass
                    stdscr.attroff(curses.color_pair(2))

                self._draw_buttons(stdscr, y + h - 2, x, w, ["Yes", "No"], btn_idx)
                stdscr.refresh()

                ch = stdscr.getch()
                if ch in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("\t"), curses.KEY_BTAB):
                    btn_idx = 1 - btn_idx
                elif ch in (10, 13, curses.KEY_ENTER, ord(" ")):
                    return btn_idx == 0
                elif ch in (ord("y"), ord("Y")):
                    return True
                elif ch in (ord("n"), ord("N"), 27):
                    return False
            return False

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Interactive Form Dialog (form)
    # ──────────────────────────────────────────────────────────────────────────
    def form(
        self,
        title: str,
        prompt: str,
        fields: List[Dict[str, Any]],
        buttons: Optional[List[str]] = None,
        width: int = 76,
        height: int = 22
    ) -> Tuple[Optional[Dict[str, str]], str]:
        """
        Interactive Multi-field Form Dialog.
        Each field item format:
        {
            "key": "cluster_name",
            "label": "Cluster Name:",
            "value": "OpenLabOps",
            "secret": False,
            "help": "Cluster identification name"
        }
        Returns (values_dict, pressed_button) or (None, "Cancel").
        """
        buttons = buttons or ["OK", "Cancel"]

        def _run(stdscr):
            self._init_colors()
            curses.curs_set(1)
            max_y, max_x = stdscr.getmaxyx()
            w = max(50, min(width, max_x - 4))
            
            prompt_lines = wrap_text(prompt, w - 6)[:4]
            num_fields = len(fields)
            num_buttons = len(buttons)
            total_elements = num_fields + num_buttons
            focus_idx = 0

            # Dynamic height calculation (reserved space for contextual hint box)
            needed_h = len(prompt_lines) + num_fields * 2 + 8
            h = min(max_y - 2, max(height, needed_h))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            val_map = {f["key"]: list(str(f.get("value", ""))) for f in fields}
            cursors = {f["key"]: len(val_map[f["key"]]) for f in fields}

            # Available rows for fields
            start_row = y + 2 + len(prompt_lines) + 1
            available_field_rows = (y + h - 6) - start_row
            field_spacing = 2 if (num_fields * 2 <= available_field_rows) else 1

            while True:
                # Help footer
                if focus_idx < num_fields:
                    help_txt = fields[focus_idx].get("help", "<Tab>/<Down> Next | <Enter> Submit | <Esc> Cancel")
                else:
                    help_txt = "<Enter> Activate Button | <Tab> Navigate | <Esc> Cancel"

                self._draw_backdrop(stdscr, help_txt)
                self._draw_box(stdscr, y, x, h, w, title)

                # Prompt description (wrapped)
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                for p_idx, p_line in enumerate(prompt_lines):
                    try:
                        stdscr.addstr(y + 2 + p_idx, x + 3, pad_to_width(p_line, w - 6))
                    except curses.error:
                        pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Render Form Fields
                max_label_w = min(26, max((str_width(f["label"]) for f in fields), default=18) + 2)
                input_w = max(10, w - max_label_w - 8)

                for i, f in enumerate(fields):
                    f_row = start_row + i * field_spacing
                    if f_row >= y + h - 5:
                        break

                    f_key = f["key"]
                    f_val_chars = val_map[f_key]
                    is_focused = (focus_idx == i)

                    # Label
                    stdscr.attron(curses.color_pair(2))
                    try:
                        stdscr.addstr(f_row, x + 3, pad_to_width(f["label"], max_label_w))
                    except curses.error:
                        pass
                    stdscr.attroff(curses.color_pair(2))

                    # Input Box
                    input_x = x + 3 + max_label_w
                    disp_str = "".join("*" if f.get("secret") else c for c in f_val_chars)

                    cur_pos = cursors[f_key]
                    disp_w = str_width(disp_str)
                    if disp_w < input_w:
                        box_content = pad_to_width(disp_str, input_w)
                    else:
                        start_pos = max(0, cur_pos - input_w + 1)
                        box_content = slice_to_width(disp_str[start_pos:], input_w)
                        box_content = pad_to_width(box_content, input_w)

                    field_color = curses.color_pair(5) if is_focused else curses.color_pair(4)
                    stdscr.attron(field_color)
                    try:
                        stdscr.addstr(f_row, input_x, box_content)
                    except curses.error:
                        pass
                    stdscr.attroff(field_color)

                # Render Contextual Help / Hint Block (Above Action Buttons)
                hint_y = y + h - 5
                if hint_y > start_row:
                    stdscr.attron(curses.color_pair(2) | curses.A_DIM)
                    try:
                        stdscr.addstr(hint_y - 1, x + 2, "─" * (w - 4))
                    except curses.error:
                        pass
                    stdscr.attroff(curses.color_pair(2) | curses.A_DIM)

                    if focus_idx < num_fields:
                        f_active = fields[focus_idx]
                        k = f_active.get("key", "").lower()
                        if k in ("role", "node_category", "inv_group_role"):
                            h_line1 = "💡 [類型說明] server: 一般伺服器 | dev: 開發端點 | desktop: 桌面工作站"
                            h_line2 = "              hypervisor: 虛擬化平台 (KVM/PVE) | storage: 網路儲存 (NAS)"
                        elif "key" in k:
                            h_line1 = "💡 [私鑰路徑] 可填私鑰絕對路徑或 ~/.ssh/ 檔名 (如 ~/.ssh/ansible.key)"
                            h_line2 = "              留空時將自動探測本機預設私鑰"
                        elif "pass" in k:
                            h_line1 = "💡 [連線密碼] 目標主機 SSH 登入密碼或 Sudo 提權密碼"
                            h_line2 = "              若目標已注入免密公鑰且 Sudo 免密可直接留空"
                        elif "user" in k:
                            h_line1 = f"💡 [帳號說明] {f_active.get('help', '目標主機之使用者帳號')}"
                            h_line2 = "              初始帳號通常為系統安裝帳號 (如 admin, ubuntu, root)"
                        elif k in ("host", "ip"):
                            h_line1 = "💡 [連線位址] 目標節點之 IPv4 位址或可解析之 FQDN 主機名稱"
                            h_line2 = "              範例: 192.168.1.11 或 node1.local"
                        else:
                            h_line1 = f"💡 {f_active.get('help', f_active.get('label', ''))}"
                            h_line2 = ""

                        stdscr.attron(curses.color_pair(5))
                        try:
                            stdscr.addstr(hint_y, x + 3, slice_to_width(h_line1, w - 6))
                            if h_line2 and hint_y + 1 < y + h - 2:
                                stdscr.addstr(hint_y + 1, x + 3, slice_to_width(h_line2, w - 6))
                        except curses.error:
                            pass
                        stdscr.attroff(curses.color_pair(5))

                # Render Action Buttons
                btn_active_idx = focus_idx - num_fields if focus_idx >= num_fields else -1
                self._draw_buttons(stdscr, y + h - 2, x, w, buttons, btn_active_idx)

                # Physical cursor positioning
                if focus_idx < num_fields:
                    curses.curs_set(1)
                    cur_f = fields[focus_idx]
                    cur_k = cur_f["key"]
                    cur_pos = cursors[cur_k]
                    f_row = start_row + focus_idx * field_spacing
                    input_x = x + 3 + max_label_w
                    disp_str = "".join("*" if cur_f.get("secret") else c for c in val_map[cur_k])
                    disp_w = str_width(disp_str)
                    if disp_w < input_w:
                        cursor_col = input_x + str_width(disp_str[:cur_pos])
                    else:
                        start_pos = max(0, cur_pos - input_w + 1)
                        cursor_col = input_x + str_width(disp_str[start_pos:cur_pos])
                    cursor_col = min(input_x + input_w - 1, max(input_x, cursor_col))
                    try:
                        stdscr.move(f_row, cursor_col)
                    except curses.error:
                        pass
                else:
                    curses.curs_set(0)

                stdscr.refresh()

                ch = stdscr.getch()

                if ch == 27:
                    stdscr.nodelay(True)
                    next_ch = stdscr.getch()
                    stdscr.nodelay(False)
                    if next_ch == -1:
                        return None, "Cancel"
                    if next_ch == ord("["):
                        code = stdscr.getch()
                        if code == ord("A"):
                            ch = curses.KEY_UP
                        elif code == ord("B"):
                            ch = curses.KEY_DOWN
                        elif code == ord("C"):
                            ch = curses.KEY_RIGHT
                        elif code == ord("D"):
                            ch = curses.KEY_LEFT
                        elif code == ord("Z"):
                            ch = curses.KEY_BTAB
                        else:
                            continue

                if ch in (ord("\t"), curses.KEY_DOWN):
                    focus_idx = (focus_idx + 1) % total_elements
                elif ch in (curses.KEY_BTAB, curses.KEY_UP):
                    focus_idx = (focus_idx - 1) % total_elements
                elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT) and focus_idx >= num_fields:
                    b_idx = focus_idx - num_fields
                    b_idx = (b_idx + (1 if ch == curses.KEY_RIGHT else -1)) % num_buttons
                    focus_idx = num_fields + b_idx

                elif focus_idx >= num_fields:
                    if ch in (10, 13, curses.KEY_ENTER, ord(" ")):
                        btn_name = buttons[focus_idx - num_fields]
                        if btn_name.lower() in ("cancel", "exit"):
                            return None, btn_name
                        res_vals = {f["key"]: "".join(val_map[f["key"]]).strip() for f in fields}
                        return res_vals, btn_name
                else:
                    cur_f = fields[focus_idx]
                    cur_k = cur_f["key"]
                    chars = val_map[cur_k]
                    c_pos = cursors[cur_k]

                    if ch in (10, 13, curses.KEY_ENTER):
                        res_vals = {f["key"]: "".join(val_map[f["key"]]).strip() for f in fields}
                        return res_vals, buttons[0]
                    elif ch in (curses.KEY_BACKSPACE, 127, 8):
                        if c_pos > 0:
                            chars.pop(c_pos - 1)
                            cursors[cur_k] -= 1
                    elif ch in (curses.KEY_DC,):
                        if c_pos < len(chars):
                            chars.pop(c_pos)
                    elif ch == curses.KEY_LEFT:
                        if c_pos > 0:
                            cursors[cur_k] -= 1
                    elif ch == curses.KEY_RIGHT:
                        if c_pos < len(chars):
                            cursors[cur_k] += 1
                    elif ch == curses.KEY_HOME:
                        cursors[cur_k] = 0
                    elif ch == curses.KEY_END:
                        cursors[cur_k] = len(chars)
                    elif 32 <= ch <= 126:
                        chars.insert(c_pos, chr(ch))
                        cursors[cur_k] += 1

            return None, "Cancel"

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 3.1 Single-Line Password/Passphrase Dialog (password_dialog)
    # ──────────────────────────────────────────────────────────────────────────
    def password_dialog(self, title: str, prompt: str, width: int = 68, height: int = 12) -> Optional[str]:
        """
        Display a single-line hidden password/passphrase prompt dialog.
        Used for in-flight interception of sudo password or SSH key passphrase.
        Returns the entered password string, or None if canceled/ESC.
        """
        def _run(stdscr):
            self._init_colors()
            curses.curs_set(1)
            max_y, max_x = stdscr.getmaxyx()
            w = max(42, min(width, max_x - 4))
            prompt_lines = wrap_text(prompt, w - 6)[:3]
            h = min(max_y - 2, max(height, len(prompt_lines) + 8))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            pw_chars: List[str] = []
            cur_pos = 0
            buttons = ["OK", "Cancel"]
            focus_btn = False
            btn_idx = 0

            input_y = y + 2 + len(prompt_lines) + 1
            input_w = max(12, w - 8)
            input_x = x + 4

            while True:
                help_text = "<Enter> Submit | <Tab> Buttons | <Esc> Cancel"
                self._draw_backdrop(stdscr, help_text)
                self._draw_box(stdscr, y, x, h, w, title)

                # Prompt lines
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                for p_idx, p_line in enumerate(prompt_lines):
                    try:
                        stdscr.addstr(y + 2 + p_idx, x + 3, pad_to_width(p_line, w - 6))
                    except curses.error:
                        pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Input box
                disp_str = "*" * len(pw_chars)
                if len(disp_str) < input_w:
                    box_content = pad_to_width(disp_str, input_w)
                else:
                    start_pos = max(0, cur_pos - input_w + 1)
                    box_content = disp_str[start_pos:start_pos + input_w]

                color = curses.color_pair(4) if focus_btn else curses.color_pair(5)
                stdscr.attron(color)
                try:
                    stdscr.addstr(input_y, input_x, box_content)
                except curses.error:
                    pass
                stdscr.attroff(color)

                # Buttons
                self._draw_buttons(stdscr, y + h - 2, x, w, buttons, btn_idx if focus_btn else -1)

                # Cursor positioning
                if not focus_btn:
                    curses.curs_set(1)
                    if len(disp_str) < input_w:
                        c_col = input_x + cur_pos
                    else:
                        start_pos = max(0, cur_pos - input_w + 1)
                        c_col = input_x + (cur_pos - start_pos)
                    try:
                        stdscr.move(input_y, min(input_x + input_w - 1, max(input_x, c_col)))
                    except curses.error:
                        pass
                else:
                    curses.curs_set(0)

                stdscr.refresh()

                ch = stdscr.getch()

                if ch == 27:
                    stdscr.nodelay(True)
                    next_ch = stdscr.getch()
                    stdscr.nodelay(False)
                    if next_ch == -1:
                        return None
                    if next_ch == ord("["):
                        code = stdscr.getch()
                        if code == ord("A"):
                            ch = curses.KEY_UP
                        elif code == ord("B"):
                            ch = curses.KEY_DOWN
                        elif code == ord("C"):
                            ch = curses.KEY_RIGHT
                        elif code == ord("D"):
                            ch = curses.KEY_LEFT
                        elif code == ord("Z"):
                            ch = curses.KEY_BTAB
                        else:
                            continue

                if ch in (ord("\t"), curses.KEY_DOWN):
                    focus_btn = not focus_btn
                elif ch in (curses.KEY_BTAB, curses.KEY_UP):
                    focus_btn = not focus_btn
                elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT) and focus_btn:
                    btn_idx = 1 - btn_idx
                elif focus_btn:
                    if ch in (10, 13, curses.KEY_ENTER, ord(" ")):
                        if buttons[btn_idx] == "OK":
                            return "".join(pw_chars)
                        return None
                else:
                    if ch in (10, 13, curses.KEY_ENTER):
                        return "".join(pw_chars)
                    elif ch in (curses.KEY_BACKSPACE, 127, 8):
                        if cur_pos > 0:
                            pw_chars.pop(cur_pos - 1)
                            cur_pos -= 1
                    elif ch in (curses.KEY_DC,):
                        if cur_pos < len(pw_chars):
                            pw_chars.pop(cur_pos)
                    elif ch == curses.KEY_LEFT:
                        if cur_pos > 0:
                            cur_pos -= 1
                    elif ch == curses.KEY_RIGHT:
                        if cur_pos < len(pw_chars):
                            cur_pos += 1
                    elif 32 <= ch <= 126:
                        pw_chars.insert(cur_pos, chr(ch))
                        cur_pos += 1

            return None

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 3.5 Menu Dialog (menu)
    # ──────────────────────────────────────────────────────────────────────────
    def menu(
        self,
        title: str,
        prompt: str,
        items: List[Tuple[str, str]],
        buttons: Optional[List[str]] = None,
        width: int = 76,
        height: int = 20,
        default_tag: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        bsdinstall-style Single-Selection Menu.
        items: List of (tag, description), e.g. [("onboard", "Onboard New Node"), ...]
        Returns (selected_tag, button) or (None, "Cancel").
        """
        buttons = buttons or ["OK", "Cancel"]

        def _run(stdscr):
            self._init_colors()
            curses.curs_set(0)
            max_y, max_x = stdscr.getmaxyx()
            w = max(50, min(width, max_x - 4))
            
            prompt_lines = wrap_text(prompt, w - 6)[:4]
            needed_h = len(prompt_lines) + len(items) + 6
            h = min(max_y - 2, max(height, min(max_y - 2, needed_h)))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            num_items = len(items)
            num_buttons = len(buttons)

            selected_idx = 0
            if default_tag:
                for idx, (t, _) in enumerate(items):
                    if t == default_tag:
                        selected_idx = idx
                        break

            scroll_offset = 0
            start_row = y + 2 + len(prompt_lines) + 1
            visible_rows = max(3, (y + h - 3) - start_row)
            focus_on_buttons = False
            active_btn_idx = 0

            # Column widths for tag and description
            tag_col_w = min(22, max(14, max((str_width(t) for t, _ in items), default=14) + 2))
            desc_col_w = max(10, w - 6 - tag_col_w - 4)

            while True:
                self._draw_backdrop(
                    stdscr,
                    "<Up>/<Down> Navigate | <Enter> Select | <Tab> Buttons | <Esc> Cancel"
                )
                self._draw_box(stdscr, y, x, h, w, title)

                # Prompt (wrapped)
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                for p_idx, p_line in enumerate(prompt_lines):
                    try:
                        stdscr.addstr(y + 2 + p_idx, x + 3, pad_to_width(p_line, w - 6))
                    except curses.error:
                        pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Menu items
                for r in range(visible_rows):
                    item_idx = scroll_offset + r
                    row_y = start_row + r
                    if item_idx >= num_items:
                        break

                    tag, desc = items[item_idx]
                    is_active = (not focus_on_buttons and item_idx == selected_idx)

                    tag_part = pad_to_width(tag, tag_col_w)
                    desc_part = slice_to_width(desc, desc_col_w)
                    line_content = f"  {tag_part} {desc_part}"
                    line_content = pad_to_width(line_content, w - 6)

                    if is_active:
                        stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                        try:
                            stdscr.addstr(row_y, x + 3, line_content)
                        except curses.error:
                            pass
                        stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
                    else:
                        stdscr.attron(curses.color_pair(2))
                        try:
                            stdscr.addstr(row_y, x + 3, line_content)
                        except curses.error:
                            pass
                        stdscr.attroff(curses.color_pair(2))

                # Scroll indicators
                if scroll_offset > 0:
                    try:
                        stdscr.addstr(start_row - 1, x + w - 5, "▲", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass
                if scroll_offset + visible_rows < num_items:
                    try:
                        stdscr.addstr(start_row + visible_rows, x + w - 5, "▼", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass

                # Buttons
                self._draw_buttons(
                    stdscr,
                    y + h - 2,
                    x,
                    w,
                    buttons,
                    active_btn_idx if focus_on_buttons else -1
                )
                stdscr.refresh()

                ch = stdscr.getch()

                if ch == 27:
                    stdscr.nodelay(True)
                    next_ch = stdscr.getch()
                    stdscr.nodelay(False)
                    if next_ch == -1:
                        return None, "Cancel"
                    if next_ch == ord("["):
                        code = stdscr.getch()
                        if code == ord("A"):
                            ch = curses.KEY_UP
                        elif code == ord("B"):
                            ch = curses.KEY_DOWN
                        elif code == ord("C"):
                            ch = curses.KEY_RIGHT
                        elif code == ord("D"):
                            ch = curses.KEY_LEFT
                        elif code == ord("Z"):
                            ch = ord("\t")
                        else:
                            continue

                if ch in (ord("\t"),):
                    focus_on_buttons = not focus_on_buttons
                elif ch in (curses.KEY_UP, ord("k")):
                    if focus_on_buttons:
                        focus_on_buttons = False
                    elif selected_idx > 0:
                        selected_idx -= 1
                        if selected_idx < scroll_offset:
                            scroll_offset = selected_idx
                elif ch in (curses.KEY_DOWN, ord("j")):
                    if not focus_on_buttons:
                        if selected_idx < num_items - 1:
                            selected_idx += 1
                            if selected_idx >= scroll_offset + visible_rows:
                                scroll_offset += 1
                        else:
                            focus_on_buttons = True
                elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT) and focus_on_buttons:
                    active_btn_idx = (active_btn_idx + (1 if ch == curses.KEY_RIGHT else -1)) % num_buttons
                elif ch in (10, 13, curses.KEY_ENTER, ord(" ")):
                    if focus_on_buttons:
                        btn_name = buttons[active_btn_idx]
                        if btn_name.lower() in ("cancel", "exit"):
                            return None, btn_name
                        if num_items > 0:
                            return items[selected_idx][0], btn_name
                        return None, btn_name
                    else:
                        if num_items > 0:
                            return items[selected_idx][0], buttons[0]
                        return None, buttons[0]

            return None, "Cancel"

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Target Node Checklist Dialog (checklist)
    # ──────────────────────────────────────────────────────────────────────────
    def checklist(
        self,
        title: str,
        prompt: str,
        items: List[Dict[str, Any]],
        buttons: Optional[List[str]] = None,
        width: int = 76,
        height: int = 22
    ) -> Tuple[Optional[List[str]], str]:
        """
        bsdinstall-style Checklist with Spacebar toggling.
        Each item format:
        {
            "id": "node1",
            "name": "node1",
            "label": "node1 (192.168.1.10)",
            "desc": "Linux Server",
            "checked": True
        }
        Returns (list_of_selected_ids, pressed_button) or (None, "Cancel").
        """
        buttons = buttons or ["OK", "Add Node", "Cancel"]

        def _run(stdscr):
            self._init_colors()
            curses.curs_set(0)
            max_y, max_x = stdscr.getmaxyx()
            w = max(50, min(width, max_x - 4))
            
            prompt_lines = wrap_text(prompt, w - 6)[:4]
            h = min(height, max_y - 2)
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            checked_states = [item.get("checked", True) for item in items]
            selected_idx = 0
            scroll_offset = 0
            
            start_row = y + 2 + len(prompt_lines) + 1
            visible_rows = max(3, (y + h - 3) - start_row)

            num_items = len(items)
            num_buttons = len(buttons)
            focus_on_buttons = False
            active_btn_idx = 0

            def _build_item_lines(it, is_chk):
                chk_box = "[*]" if is_chk else "[ ]"
                it_label = str(it.get("label") or it.get("name") or it.get("id") or "")
                it_desc = str(it.get("desc", "")).strip()

                lines = []
                # 第一行：勾選框與主標籤（完整顯示）
                lines.append((f"  {chk_box} {it_label}", True))
                # 換行縮排完整顯示說明，不截斷
                if it_desc:
                    desc_max_w = max(10, w - 6 - 6)
                    for dl in wrap_text(it_desc, desc_max_w):
                        lines.append((f"      {dl}", False))
                return lines

            while True:
                item_lines_cache = [_build_item_lines(it, checked_states[i]) for i, it in enumerate(items)]
                item_heights = [len(l) for l in item_lines_cache]

                def _lines_needed(s_idx, e_idx):
                    if s_idx > e_idx or s_idx >= num_items:
                        return 0
                    return sum(item_heights[k] for k in range(s_idx, min(num_items, e_idx + 1)))

                self._draw_backdrop(
                    stdscr,
                    "<Space> Toggle [X] | <a> Select/Deselect All | <Tab> Buttons | <Enter> Confirm"
                )
                self._draw_box(stdscr, y, x, h, w, title)

                # Prompt header (wrapped)
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                for p_idx, p_line in enumerate(prompt_lines):
                    try:
                        stdscr.addstr(y + 2 + p_idx, x + 3, pad_to_width(p_line, w - 6))
                    except curses.error:
                        pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Checklist items list window (multi-line options with wrapped descriptions)
                cur_row = start_row
                for item_idx in range(scroll_offset, num_items):
                    if cur_row >= start_row + visible_rows:
                        break
                    lines = item_lines_cache[item_idx]
                    is_active = (not focus_on_buttons and item_idx == selected_idx)
                    is_chk = checked_states[item_idx]

                    for l_idx, (text_content, is_title) in enumerate(lines):
                        if cur_row >= start_row + visible_rows:
                            break
                        padded_text = pad_to_width(text_content, w - 6)

                        if is_active:
                            color = (curses.color_pair(3) | curses.A_BOLD) if is_title else curses.color_pair(3)
                        else:
                            if is_title:
                                color = (curses.color_pair(2) | curses.A_BOLD) if is_chk else (curses.color_pair(2) | curses.A_DIM)
                            else:
                                color = curses.color_pair(2) | curses.A_DIM

                        stdscr.attron(color)
                        try:
                            stdscr.addstr(cur_row, x + 3, padded_text)
                        except curses.error:
                            pass
                        stdscr.attroff(color)
                        cur_row += 1

                # 清除內部剩餘列空間
                while cur_row < start_row + visible_rows:
                    try:
                        stdscr.addstr(cur_row, x + 3, " " * (w - 6), curses.color_pair(2))
                    except curses.error:
                        pass
                    cur_row += 1

                # Scroll indicators
                if scroll_offset > 0:
                    try:
                        stdscr.addstr(start_row - 1, x + w - 5, "▲", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass
                if _lines_needed(scroll_offset, num_items - 1) > visible_rows:
                    try:
                        stdscr.addstr(start_row + visible_rows, x + w - 5, "▼", curses.color_pair(6) | curses.A_BOLD)
                    except curses.error:
                        pass

                # Action Buttons
                self._draw_buttons(
                    stdscr,
                    y + h - 2,
                    x,
                    w,
                    buttons,
                    active_btn_idx if focus_on_buttons else -1
                )
                stdscr.refresh()

                ch = stdscr.getch()

                if ch == 27:
                    stdscr.nodelay(True)
                    next_ch = stdscr.getch()
                    stdscr.nodelay(False)
                    if next_ch == -1:
                        return None, "Cancel"
                    if next_ch == ord("["):
                        code = stdscr.getch()
                        if code == ord("A"):
                            ch = curses.KEY_UP
                        elif code == ord("B"):
                            ch = curses.KEY_DOWN
                        elif code == ord("C"):
                            ch = curses.KEY_RIGHT
                        elif code == ord("D"):
                            ch = curses.KEY_LEFT
                        elif code == ord("Z"):
                            ch = ord("\t")
                        else:
                            continue

                # Navigation Keys
                if ch in (ord("\t"),):
                    focus_on_buttons = not focus_on_buttons
                elif ch in (curses.KEY_UP, ord("k")):
                    if focus_on_buttons:
                        focus_on_buttons = False
                    elif selected_idx > 0:
                        selected_idx -= 1
                        if selected_idx < scroll_offset:
                            scroll_offset = selected_idx
                elif ch in (curses.KEY_DOWN, ord("j")):
                    if not focus_on_buttons:
                        if selected_idx < num_items - 1:
                            selected_idx += 1
                            while scroll_offset < selected_idx and _lines_needed(scroll_offset, selected_idx) > visible_rows:
                                scroll_offset += 1
                        else:
                            focus_on_buttons = True
                elif ch in (curses.KEY_PPAGE,):
                    if not focus_on_buttons:
                        selected_idx = max(0, selected_idx - 3)
                        if selected_idx < scroll_offset:
                            scroll_offset = selected_idx
                elif ch in (curses.KEY_NPAGE,):
                    if not focus_on_buttons:
                        selected_idx = min(num_items - 1, selected_idx + 3)
                        while scroll_offset < selected_idx and _lines_needed(scroll_offset, selected_idx) > visible_rows:
                            scroll_offset += 1
                elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT) and focus_on_buttons:
                    active_btn_idx = (active_btn_idx + (1 if ch == curses.KEY_RIGHT else -1)) % num_buttons
                elif ch == ord(" ") and not focus_on_buttons:
                    if num_items > 0:
                        checked_states[selected_idx] = not checked_states[selected_idx]
                elif ch in (ord("a"), ord("A")) and not focus_on_buttons:
                    any_checked = any(checked_states)
                    checked_states = [not any_checked] * num_items
                elif ch in (10, 13, curses.KEY_ENTER):
                    if focus_on_buttons:
                        btn_name = buttons[active_btn_idx]
                        if btn_name.lower() in ("cancel", "exit"):
                            return None, btn_name
                        elif btn_name == "Add Node":
                            selected_ids = [items[i]["id"] for i in range(num_items) if checked_states[i]]
                            return selected_ids, "Add Node"
                        else:
                            selected_ids = [items[i]["id"] for i in range(num_items) if checked_states[i]]
                            return selected_ids, btn_name
                    else:
                        selected_ids = [items[i]["id"] for i in range(num_items) if checked_states[i]]
                        return selected_ids, buttons[0]
                elif ch == 27:
                    return None, "Cancel"

            return None, "Cancel"

        return self._run_modal(_run)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Live Progress Streamer Box (progress_box)
    # ──────────────────────────────────────────────────────────────────────────
    def progress_box(
        self,
        title: str,
        task_name: str,
        runner_fn: Callable[[Callable[[str], None]], bool],
        width: int = 76,
        height: int = 22
    ) -> bool:
        """
        Executes a task callback while rendering a live scrolling console inside a bsdinstall dialog box.
        runner_fn receives `log(msg)` function to push status lines in real-time.
        """
        def _run(stdscr):
            self._init_colors()
            curses.curs_set(0)
            max_y, max_x = stdscr.getmaxyx()
            h = min(height, max_y - 2)
            w = max(50, min(width, max_x - 4))
            y = max(1, (max_y - h) // 2)
            x = max(2, (max_x - w) // 2)

            log_lines: List[str] = []

            def _log(line: str):
                for sub_l in str(line).split("\n"):
                    clean = strip_ansi(sub_l)
                    if not clean:
                        continue
                    for wrapped_l in wrap_text(clean, w - 6):
                        log_lines.append(wrapped_l)

                self._draw_backdrop(stdscr, "Running task in background... Please wait.")
                self._draw_box(stdscr, y, x, h, w, title)

                # Render task header
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                try:
                    stdscr.addstr(y + 2, x + 3, pad_to_width(f"• Task: {task_name}", w - 6))
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

                # Render scrolling logs
                visible_log_h = max(2, h - 6)
                display_slice = log_lines[-visible_log_h:]
                for row_idx, clean_l in enumerate(display_slice):
                    color = curses.color_pair(2)
                    if "[✓]" in clean_l or "OK" in clean_l:
                        color = curses.color_pair(8) | curses.A_BOLD
                    elif "[✗]" in clean_l or "Error" in clean_l or "Failed" in clean_l or "WARNING" in clean_l:
                        color = curses.color_pair(9) | curses.A_BOLD

                    stdscr.attron(color)
                    try:
                        stdscr.addstr(y + 4 + row_idx, x + 3, pad_to_width(clean_l, w - 6))
                    except curses.error:
                        pass
                    stdscr.attroff(color)

                stdscr.refresh()

            _log("Starting preflight verification...")
            time.sleep(0.1)

            success = runner_fn(_log)

            # Finished: render button to continue
            status_text = "Task Completed Successfully! Press < Continue >." if success else "Task Encountered Warnings/Errors! Press < Continue >."
            _log(status_text)

            while True:
                self._draw_buttons(stdscr, y + h - 2, x, w, ["Continue"], 0)
                stdscr.refresh()
                ch = stdscr.getch()
                if ch in (10, 13, curses.KEY_ENTER, ord(" "), 27):
                    break

            return success

        return self._run_modal(_run)
