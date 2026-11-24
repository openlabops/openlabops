#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Core Library: Modern TUI & Terminal UI Components
Zero External Dependencies: 100% Python Standard Library [INV-01].
Provides Unicode box-drawing menus, arrow-key navigation, i18n prompts, and spinners.
"""

import os
import sys
import time
import threading
import unicodedata
from typing import List, Tuple, Optional

from .ui_theme import C_CYAN, C_YELLOW, C_BOLD, C_RESET, C_DIM, C_GREEN, C_RED, ui_warn, char_width, str_width


# Try to import i18n translator safely
try:
    from .i18n import t
except Exception:
    def t(keypath: str, default: str = None, **kwargs) -> str:
        return default or keypath


def _center_cjk(text: str, target_width: int) -> str:
    w = str_width(text)
    if w >= target_width:
        return text
    total_pad = target_width - w
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    return (" " * left_pad) + text + (" " * right_pad)


def _ljust_cjk(text: str, target_width: int) -> str:
    w = str_width(text)
    if w >= target_width:
        return text
    return text + (" " * (target_width - w))


def ui_box_header(title: str, subtitle: Optional[str] = None, width: int = 70):
    """繪製具有 Unicode 圓角邊框之現代化標題橫幅"""
    sub_w = str_width(subtitle) if subtitle else 0
    line_w = max(width, str_width(title) + 8, sub_w + 8)
    print(f"\n{C_CYAN}{C_BOLD}╭{'─' * (line_w - 2)}╮{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}│{C_RESET}  {C_BOLD}{_center_cjk(title, line_w - 6)}{C_RESET}  {C_CYAN}{C_BOLD}│{C_RESET}")
    if subtitle:
        print(f"{C_CYAN}{C_BOLD}│{C_RESET}  {C_DIM}{_center_cjk(subtitle, line_w - 6)}{C_RESET}  {C_CYAN}{C_BOLD}│{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}╰{'─' * (line_w - 2)}╯{C_RESET}\n")


def ui_confirm(prompt: Optional[str] = None, default: str = "n") -> bool:
    """顯示兼具 i18n 與預設值之確認對話框"""
    if prompt is None:
        prompt = t("common.confirm_prompt", "確定要繼續嗎？")

    if default.lower() in ("y", "yes"):
        prompt_str = f"{prompt} [Y/n]: "
    else:
        prompt_str = f"{prompt} [y/N]: "

    while True:
        try:
            choice = input(f"{C_YELLOW}{C_BOLD}?{C_RESET} {prompt_str}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return False

        if not choice:
            choice = default

        if choice.lower() in ("y", "yes"):
            return True
        elif choice.lower() in ("n", "no"):
            return False
        else:
            print(f"  {C_DIM}請輸入 y 或 n (Please enter 'y' or 'n'){C_RESET}")


def _read_single_key() -> str:
    """
    從終端機讀取單一按鍵 (支援方向鍵與標準 ASCII)。
    若非 TTY 或不支援 termios 則退回安全標準讀取。
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line.strip()

    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # 處理 ANSI Escape Sequence (如方向鍵)
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "UP"
                    elif ch3 == "B":
                        return "DOWN"
                    elif ch3 == "C":
                        return "RIGHT"
                    elif ch3 == "D":
                        return "LEFT"
                return "ESC"
            elif ch in ("\r", "\n"):
                return "ENTER"
            elif ch == " ":
                return "SPACE"
            elif ch == "\t":
                return "TAB"
            elif ch in ("\x7f", "\x08"):
                return "BACKSPACE"
            elif ch == "\x13":
                return "CTRL_S"
            elif ch in ("\x03", "\x04"):
                return "CTRL_C"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        # Fallback for environments without termios
        return sys.stdin.readline().strip()


def ui_select(title: str, options: List[str], default_idx: int = 1) -> Tuple[int, str]:
    """
    高階 TUI 選單：
    支援方向鍵 (↑/↓/j/k) 即時高亮捲動，亦支援直接輸入數字編號選取。
    """
    num_options = len(options)
    if num_options == 0:
        return 0, ""

    # 若非 TTY (例如管線或 CI)，直接退回純文字編號輸入
    if not sys.stdin.isatty():
        print(f"\n{C_CYAN}{C_BOLD}{title}{C_RESET}")
        for i, opt in enumerate(options, 1):
            print(f"  [{i}] {opt}")
        try:
            choice_str = input(f"請輸入選項 [1-{num_options}]: ").strip()
            if choice_str.isdigit():
                c = int(choice_str)
                if 1 <= c <= num_options:
                    return c, options[c - 1]
        except (KeyboardInterrupt, EOFError):
            pass
        return 1, options[0]

    current_idx = max(1, min(default_idx, num_options))
    first_render = True

    while True:
        # 計算邊框與渲染
        max_opt_len = max(str_width(opt) for opt in options)
        box_width = max(60, max_opt_len + 12, str_width(title) + 6)
        lines_count = num_options + 3

        if not first_render:
            # 清除先前印出的選單行數 (頂框 + 各選項 + 底框 + 提示行)
            sys.stdout.write(f"\033[{lines_count}A\r")

        first_render = False

        # 輸出現代化 Unicode 卡片
        top_dashes = "─" * max(0, box_width - str_width(title) - 5)
        print(f"{C_CYAN}{C_BOLD}╭─ {title} {top_dashes}╮{C_RESET}\033[K")
        for i, opt in enumerate(options, 1):
            opt_w = str_width(opt)
            padding = " " * max(0, box_width - opt_w - 9)
            if i == current_idx:
                prefix = f"{C_GREEN}{C_BOLD}  ➜ [{i}] {C_RESET}"
                line_content = f"{C_BOLD}{C_GREEN}{opt}{C_RESET}"
                print(f"{C_CYAN}│{C_RESET}{prefix}{line_content}{padding}{C_CYAN}│{C_RESET}\033[K")
            else:
                prefix = f"    [{i}] "
                print(f"{C_CYAN}│{C_RESET}{prefix}{opt}{padding}{C_CYAN}│{C_RESET}\033[K")
        print(f"{C_CYAN}{C_BOLD}╰{'─' * (box_width - 2)}╯{C_RESET}\033[K")
        prompt_tip = t("common.tui_nav_tip", "[↑/↓/j/k] 導航  [1-9] 直選  [Enter] 確認  [q] 離開")
        print(f"{C_DIM}{prompt_tip}{C_RESET}\033[K")
        sys.stdout.flush()

        key = _read_single_key()
        if key in ("UP", "k", "K"):
            current_idx = current_idx - 1 if current_idx > 1 else num_options
        elif key in ("DOWN", "j", "J"):
            current_idx = current_idx + 1 if current_idx < num_options else 1
        elif key == "ENTER":
            print()
            return current_idx, options[current_idx - 1]
        elif key in ("q", "Q", "ESC", "CTRL_C"):
            print()
            sys.exit(0)
        elif key.isdigit():
            c = int(key)
            if 1 <= c <= num_options:
                print()
                return c, options[c - 1]


def ui_checklist(
    title: str,
    options: List[str],
    checked_indices: Optional[List[int]] = None,
    tip: Optional[str] = None
) -> List[int]:
    """
    bsdinstall / dialog 風格之 TUI 多選核取清單 (Checklist)：
    - [↑/↓/j/k] 上下導航
    - [Space] 切換核取狀態 [X] / [ ]
    - [a/A] 全選 / 全取消 (Toggle All)
    - [Enter] 確定送出 (回傳選中項目索引列表，1-based)
    - [q/ESC] 放棄離開 (回傳空列表)
    100% Python 標準庫，零外部依賴 [INV-01]。
    """
    num_options = len(options)
    if num_options == 0:
        return []

    checked_set = set(checked_indices or [])

    # 若非 TTY (例如 CI 或管線)，退回純文字輸入模式
    if not sys.stdin.isatty():
        print(f"\n{C_CYAN}{C_BOLD}{title}{C_RESET}")
        for i, opt in enumerate(options, 1):
            mark = "[X]" if i in checked_set else "[ ]"
            print(f"  {mark} [{i}] {opt}")
        try:
            raw = input(f"請輸入核取編號 (以逗號分隔，例如 1,3；或直接 Enter 維持預設): ").strip()
            if not raw:
                return sorted(list(checked_set))
            if raw.lower() in ("all", "a"):
                return list(range(1, num_options + 1))
            if raw.lower() in ("none", "n"):
                return []
            selected = []
            for part in raw.split(","):
                part = part.strip()
                if part.isdigit() and 1 <= int(part) <= num_options:
                    selected.append(int(part))
            return sorted(list(set(selected)))
        except (KeyboardInterrupt, EOFError):
            return sorted(list(checked_set))

    current_idx = 1
    first_render = True

    while True:
        max_opt_len = max(str_width(opt) for opt in options)
        box_width = max(66, max_opt_len + 14, str_width(title) + 8)
        lines_count = num_options + 3

        if not first_render:
            sys.stdout.write(f"\033[{lines_count}A\r")

        first_render = False

        # 輸出 Unicode 卡片 (Dialog Checklist Style)
        top_dashes = "─" * max(0, box_width - str_width(title) - 5)
        print(f"{C_CYAN}{C_BOLD}╭─ {title} {top_dashes}╮{C_RESET}\033[K")
        for i, opt in enumerate(options, 1):
            is_active = (i == current_idx)
            is_checked = (i in checked_set)
            
            box_mark = f"{C_GREEN}[X]{C_RESET}" if is_checked else f"{C_DIM}[ ]{C_RESET}"
            opt_w = str_width(opt)
            padding = " " * max(0, box_width - opt_w - 13)
            
            if is_active:
                cursor = f"{C_GREEN}{C_BOLD}➜ {C_RESET}"
                line_content = f"{C_BOLD}{opt}{C_RESET}"
                print(f"{C_CYAN}│{C_RESET}  {cursor}{box_mark} {line_content}{padding}{C_CYAN}│{C_RESET}\033[K")
            else:
                cursor = "  "
                print(f"{C_CYAN}│{C_RESET}  {cursor}{box_mark} {opt}{padding}{C_CYAN}│{C_RESET}\033[K")
        print(f"{C_CYAN}{C_BOLD}╰{'─' * (box_width - 2)}╯{C_RESET}\033[K")

        nav_tip = tip or "[↑/↓/j/k] 移動  [Space] 勾選 [X]  [a] 全選  [Enter] 確定  [q] 離開"
        print(f"{C_DIM}{nav_tip}{C_RESET}\033[K")
        sys.stdout.flush()

        key = _read_single_key()
        if key in ("UP", "k", "K"):
            current_idx = current_idx - 1 if current_idx > 1 else num_options
        elif key in ("DOWN", "j", "J"):
            current_idx = current_idx + 1 if current_idx < num_options else 1
        elif key in ("SPACE", " "):
            if current_idx in checked_set:
                checked_set.remove(current_idx)
            else:
                checked_set.add(current_idx)
        elif key in ("a", "A"):
            if len(checked_set) == num_options:
                checked_set.clear()
            else:
                checked_set = set(range(1, num_options + 1))
        elif key == "ENTER":
            print()
            return sorted(list(checked_set))
        elif key in ("q", "Q", "ESC", "CTRL_C"):
            print()
            return []
        elif key.isdigit():
            c = int(key)
            if 1 <= c <= num_options:
                if c in checked_set:
                    checked_set.remove(c)
                else:
                    checked_set.add(c)


def ui_form(
    title: str,
    fields: List[dict],
    tip: Optional[str] = None
) -> Optional[dict]:
    """
    bsdinstall / dialog 風格之表單填寫元件 (Modern Form Dialog):
    fields 格式範例:
    [
        {"key": "host", "label": "目標主機 IP", "value": "172.28.0.10"},
        {"key": "port", "label": "SSH 埠號", "value": "22"},
        {"key": "user", "label": "初始登入帳號", "value": "labadmin"},
        {"key": "password", "label": "初始連線密碼", "value": "", "secret": True},
        {"key": "target_user", "label": "目標管理帳號", "value": "lab"},
    ]
    支援:
    - [↑/↓/Tab] 垂直切換欄位
    - 直接鍵盤鍵入即時修改、Backspace 刪除
    - [secret: True] 密碼欄位以星號 (*) 掩碼保護
    - 游標移至 [ 🚀 確定執行 (Submit) ] 按 Enter 或按 [Ctrl+S] 提交表單
    - 游標移至 [ ❌ 放棄取消 (Cancel) ] 按 Enter 或按 [ESC / Ctrl+C] 取消 (回傳 None)
    - 非 TTY (CI / 管線) 自動退回逐項提示模式
    100% Python 標準庫，零外部依賴 [INV-01]。
    """
    form_data = [dict(f) for f in fields]
    num_fields = len(form_data)
    if num_fields == 0:
        return {}

    # 若非 TTY，退回安全輸入
    if not sys.stdin.isatty():
        print(f"\n{C_CYAN}{C_BOLD}╭─ {title} ─╮{C_RESET}")
        res = {}
        for f in form_data:
            d_val = f.get("value", "")
            prompt = f"  • {f['label']} [{d_val}]: "
            try:
                val = input(prompt).strip()
                res[f["key"]] = val if val else d_val
            except (KeyboardInterrupt, EOFError):
                res[f["key"]] = d_val
        return res

    current_row = 0  # 0 .. num_fields-1 (fields), num_fields (submit), num_fields+1 (cancel)
    total_rows = num_fields + 2
    first_render = True

    # 計算最長標籤寬度
    max_label_len = max(str_width(f["label"]) for f in form_data)
    box_width = max(68, max_label_len + 42, str_width(title) + 8)
    val_box_width = box_width - max_label_len - 14

    while True:
        if not first_render:
            # 清除先前繪製行數 (頂框 1 + 欄位 num_fields + 空行 1 + 按鈕 1 + 底框 1 = num_fields + 4)
            lines_to_clear = num_fields + 4
            sys.stdout.write(f"\033[{lines_to_clear}A\r")

        first_render = False

        # 輸出現代化 Unicode 表單卡片
        print(f"{C_CYAN}{C_BOLD}╭─ {title} {'─' * max(0, box_width - str_width(title) - 5)}╮{C_RESET}\033[K")
        for i, f in enumerate(form_data):
            is_active = (i == current_row)
            lbl = _ljust_cjk(f["label"], max_label_len)
            raw_val = str(f.get("value", ""))
            disp_val = ("*" * len(raw_val)) if f.get("secret") else raw_val
            # 避免超長輸入撐破框線導致終端換行錯位
            max_disp = max(4, val_box_width - (1 if is_active else 0))
            while str_width(disp_val) > max_disp and len(disp_val) > 1:
                disp_val = disp_val[1:]
            disp_w = str_width(disp_val)

            if is_active:
                cursor = f"{C_GREEN}{C_BOLD}➜ {C_RESET}"
                field_content = f"{disp_val}█"
                val_pad = " " * max(0, val_box_width - disp_w - 1)
                val_box = f"{C_GREEN}[ {C_BOLD}{field_content}{C_RESET}{val_pad}{C_GREEN} ]{C_RESET}"
                print(f"{C_CYAN}│{C_RESET}  {cursor}{C_BOLD}{lbl}{C_RESET} : {val_box} {C_CYAN}│{C_RESET}\033[K")
            else:
                cursor = "  "
                val_pad = " " * max(0, val_box_width - disp_w)
                val_box = f"{C_DIM}[ {disp_val}{val_pad} ]{C_RESET}"
                print(f"{C_CYAN}│{C_RESET}  {cursor}{lbl} : {val_box} {C_CYAN}│{C_RESET}\033[K")

        print(f"{C_CYAN}│{' ' * (box_width - 2)}│{C_RESET}\033[K")

        # 按鈕列
        submit_lbl = "[ 🚀 確定執行 (Submit) ]"
        cancel_lbl = "[ ❌ 取消 (Cancel) ]"
        submit_btn = f"{C_GREEN}{C_BOLD}{submit_lbl}{C_RESET}" if current_row == num_fields else f"{C_DIM}{submit_lbl}{C_RESET}"
        cancel_btn = f"{C_RED}{C_BOLD}{cancel_lbl}{C_RESET}" if current_row == num_fields + 1 else f"{C_DIM}{cancel_lbl}{C_RESET}"
        btn_line = f"  {submit_btn}    {cancel_btn}"
        btn_raw_len = 2 + str_width(submit_lbl) + 4 + str_width(cancel_lbl)
        btn_padding = " " * max(0, box_width - btn_raw_len - 2)
        print(f"{C_CYAN}│{C_RESET}{btn_line}{btn_padding}{C_CYAN}│{C_RESET}\033[K")
        print(f"{C_CYAN}{C_BOLD}╰{'─' * (box_width - 2)}╯{C_RESET}\033[K")

        nav_tip = tip or "[↑/↓/Tab] 移動  [鍵入] 編輯  [Backspace] 刪除  [Enter] 下一欄/提交  [ESC] 取消"
        sys.stdout.write(f"{C_DIM}{nav_tip}{C_RESET}\033[K")
        sys.stdout.flush()

        key = _read_single_key()
        if key == "UP" or (current_row >= num_fields and key in ("k", "K")):
            current_row = (current_row - 1) if current_row > 0 else (total_rows - 1)
        elif key in ("DOWN", "TAB") or (current_row >= num_fields and key in ("j", "J")):
            current_row = (current_row + 1) if current_row < (total_rows - 1) else 0
        elif key == "BACKSPACE":
            if current_row < num_fields:
                curr_val = str(form_data[current_row].get("value", ""))
                if curr_val:
                    form_data[current_row]["value"] = curr_val[:-1]
        elif key in ("CTRL_S",):
            print()
            return {f["key"]: f.get("value", "") for f in form_data}
        elif key == "ENTER":
            if current_row == num_fields:
                # 點選 Submit 按鈕
                print()
                return {f["key"]: f.get("value", "") for f in form_data}
            elif current_row == num_fields + 1:
                # 點選 Cancel 按鈕
                print()
                return None
            else:
                # 移動至下一欄
                current_row += 1
        elif key in ("ESC", "CTRL_C"):
            print()
            return None
        else:
            # 一般可列印文字鍵入
            if current_row < num_fields and len(key) == 1 and key.isprintable():
                curr_val = str(form_data[current_row].get("value", ""))
                form_data[current_row]["value"] = curr_val + key


def select_target_hosts(
    title: str = "請選擇目標伺服器節點",
    snapshot_nodes: Optional[List[dict]] = None,
    default_all: bool = True
) -> List[str]:
    """
    BSD 風格階層式主機選擇器 (Hierarchical Target Host Selector):
    第 1 層：選擇過濾維度 (全選、依群組/作業系統篩選、手動核取清冊)
    第 2 層：若依群組篩選，進入群組清單選取後自動展開該組節點核取清單細調
    """
    nodes = snapshot_nodes or []
    if not nodes:
        from pathlib import Path
        import json
        snap_paths = [
            Path.home() / "openlabops" / "conf" / "nodes" / "current.json",
            Path.home() / "openlabops" / "conf" / "nodes" / "current.json",
            Path("/usr/local/bin/openlab/conf/current.json"),
        ]
        for sp in snap_paths:
            if sp.exists():
                try:
                    nodes = json.loads(sp.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass

    if not nodes:
        manual = input(f"{title} (手動輸入主機名，以逗號分隔): ").strip()
        return [h.strip() for h in manual.split(",") if h.strip()]

    all_hostnames = [n.get("hostname") for n in nodes if n.get("hostname")]

    options = [
        f"🌐 [All] 全選所有在線節點 (共 {len(all_hostnames)} 台)",
        "🏷️ [Group] 依角色或作業系統類別篩選 (By Category / Distro)",
        "🖥️ [Checklist] 自選節點核取清單 (Checklist 逐台勾選)",
        "❌ 取消放棄"
    ]

    choice_idx, _ = ui_select(f"{title} - 選擇篩選模式:", options)

    if choice_idx == 1:
        return all_hostnames

    elif choice_idx == 2:
        # 聚集群組 (Category & Distribution)
        groups = {}
        for n in nodes:
            h = n.get("hostname")
            cat = n.get("node_category", "server")
            dist = n.get("distribution", n.get("os_family", "Linux"))
            cat_k = f"角色: {cat}"
            dist_k = f"系統: {dist}"
            groups.setdefault(cat_k, []).append(h)
            groups.setdefault(dist_k, []).append(h)

        group_keys = list(groups.keys())
        group_opts = [f"{gk} ({len(groups[gk])} 台: {', '.join(groups[gk][:3])}...)" for gk in group_keys]
        group_opts.append("⬅️ 返回上一層")

        g_idx, _ = ui_select("請選擇欲操作的主機群組:", group_opts)
        if g_idx > len(group_keys):
            return select_target_hosts(title, nodes, default_all)

        selected_group = group_keys[g_idx - 1]
        target_group_hosts = groups[selected_group]

        # 展開該群組的 Checklist 供最後微調
        chk_options = [f"{n.get('hostname')} ({n.get('primary_ip', '')})" for n in nodes if n.get("hostname") in target_group_hosts]
        chk_hosts = [n.get("hostname") for n in nodes if n.get("hostname") in target_group_hosts]
        
        checked = ui_checklist(
            f"群組 [{selected_group}] 成員微調 (空白鍵切換 [X]):",
            chk_options,
            checked_indices=list(range(1, len(chk_options) + 1))
        )
        return [chk_hosts[i - 1] for i in checked]

    elif choice_idx == 3:
        chk_options = [f"{n.get('hostname', '')} ({n.get('primary_ip', '')}) [{n.get('node_category', 'server')}]" for n in nodes]
        default_checked = list(range(1, len(nodes) + 1)) if default_all else []
        checked = ui_checklist(title, chk_options, checked_indices=default_checked)
        return [all_hostnames[i - 1] for i in checked]

    else:
        return []


class ui_spinner:
    """Spinner 動畫提示 context manager"""
    def __init__(self, msg: Optional[str] = None):
        self.msg = msg or t("common.processing", "處理中...")
        self.running = False
        self.thread = None

    def _spin(self):
        spin_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        idx = 0
        while self.running:
            sys.stdout.write(f"\r{C_CYAN}{spin_chars[idx % len(spin_chars)]}{C_RESET} {self.msg}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def __enter__(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.thread:
            self.thread.join()
