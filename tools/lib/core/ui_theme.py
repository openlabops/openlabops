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
    """計算單個字元終端顯示寬度 (全形 CJK 與部分符號為 2，其餘為 1)。"""
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def str_width(s: str) -> int:
    """計算字串於終端之實質顯示寬度 (考量 CJK 全形與 ANSI 碼)。"""
    clean = strip_ansi(s)
    return sum(char_width(c) for c in clean)



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
