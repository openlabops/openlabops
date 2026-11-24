#!/usr/bin/env python3
"""
OpenLabOps Core Library: UI Theme & Terminal Color Utilities
"""

import sys
import re
import unicodedata

# ANSI Escape Sequences
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"

C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"


def strip_ansi(s: str) -> str:
    """去除 ANSI escape sequence 與 carriage return。"""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s).replace("\r", "")


def char_width(ch: str) -> int:
    """計算單個字元終端顯示寬度 (全形 CJK、Emoji 與部分符號為 2，變體選擇符為 0，其餘為 1)。"""
    cp = ord(ch)
    if cp in (0xFE0E, 0xFE0F) or (0xE0100 <= cp <= 0xE01EF):
        return 0
    if (0x1F300 <= cp <= 0x1FAFF) or (0x1F000 <= cp <= 0x1F02F) or (0x1F0A0 <= cp <= 0x1F0FF):
        return 2
    if cp in (0x26A0, 0x23F3, 0x231B, 0x2615, 0x2705):
        return 2
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def str_width(s: str) -> int:
    """計算字串於終端之實質顯示寬度 (考量 CJK 全形與 ANSI 碼)。"""
    clean = strip_ansi(s)
    return sum(char_width(c) for c in clean)


def pad_cjk(s: str, w: int) -> str:
    """依照終端顯示寬度向右補空格。"""
    diff = w - str_width(s)
    return s + (" " * diff) if diff > 0 else s


def truncate_cjk(s: str, max_w: int) -> str:
    """依終端顯示寬度安全截斷字串 (支援中英文與符號)。"""
    if str_width(s) <= max_w:
        return s
    res = ""
    for ch in s:
        if str_width(res + ch + "…") > max_w:
            break
        res += ch
    return res + "…"



def ui_header(title: str):
    divider = "=" * 60
    print(f"\n{C_CYAN}{C_BOLD}{divider}{C_RESET}")
    print(f"{C_BOLD}  {title}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{divider}{C_RESET}\n")


def ui_info(msg: str):
    print(f"{C_BLUE}[INFO]{C_RESET} {msg}")


def ui_success(msg: str):
    print(f"{C_GREEN}[SUCCESS]{C_RESET} {msg}")


def ui_warn(msg: str):
    print(f"{C_YELLOW}[WARN]{C_RESET} {msg}")


def ui_error(msg: str):
    print(f"{C_RED}[ERROR]{C_RESET} {msg}", file=sys.stderr)


def ui_kv(key: str, val: str):
    print(f"{C_BOLD}{key:<12}:{C_RESET} {C_CYAN}{val}{C_RESET}")


def ui_divider():
    print(f"{C_DIM}{'-' * 60}{C_RESET}")
