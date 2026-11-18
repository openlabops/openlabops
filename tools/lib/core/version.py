#!/usr/bin/env python3
"""
OpenLabOps Core Library: Version Management & Check Utilities
提供全網工具鏈單一真相源 (SSOT) 版本號查詢、語意化版本比對 (Semantic Versioning)
以及遠端 Gitea 最新版本探測功能。
"""

import os
import sys
from pathlib import Path
import urllib.request
import urllib.error

TOOL_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
if TOOL_ROOT not in sys.path:
    sys.path.insert(0, TOOL_ROOT)

from core.gitea_api import load_gitea_token, GITEA_URL, REPO_OWNER

FALLBACK_VERSION = "1.0.0"
VERSION_CANDIDATES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "VERSION")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "VERSION")),
    "/usr/local/bin/openlab/VERSION",
    str(Path.home() / "openlabops" / "VERSION"),
    str(Path.home() / "openlabops" / "tools" / "VERSION"),
    str(Path.home() / "openlab-tools" / "VERSION"),
]


def get_local_version() -> str:
    """讀取本地安裝或開發工作區之 VERSION 檔案"""
    for candidate in VERSION_CANDIDATES:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                    if ver:
                        return ver
            except Exception:
                pass
    return FALLBACK_VERSION


def get_remote_version() -> str:
    """透過 Gitea REST API 獲取遠端倉庫最新 VERSION 內容 (優先檢查 operations 聯邦倉庫，回退母體與歷史 tools 庫)"""
    token = load_gitea_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    for repo_name in ("openlab-operations", "openlabops"):
        raw_url = f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{repo_name}/raw/VERSION"
        try:
            req = urllib.request.Request(raw_url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    ver = resp.read().decode("utf-8").strip()
                    if ver:
                        return ver
        except Exception:
            pass
    return ""


def parse_version(ver_str: str) -> tuple:
    """解析語意化版本字串，支援 Pre-release 標籤比對 (e.g. 'v0.5.0-beta' -> ((0, 5, 0), 0, ((1, 'beta'),)))"""
    clean_ver = ver_str.lstrip("v").strip().split("+", 1)[0]
    if "-" in clean_ver:
        core_part, pre_part = clean_ver.split("-", 1)
    else:
        core_part, pre_part = clean_ver, ""

    parts = []
    for p in core_part.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)

    if not pre_part:
        return (tuple(parts[:3]), 1, ())

    pre_tokens = []
    for tok in pre_part.split("."):
        if tok.isdigit():
            pre_tokens.append((0, int(tok)))
        else:
            pre_tokens.append((1, tok))
    return (tuple(parts[:3]), 0, tuple(pre_tokens))


def compare_versions(v1: str, v2: str) -> int:
    """
    比對兩版本號 (v1 vs v2):
    回傳 1  表示 v1 > v2 (v1 較新)
    回傳 -1 表示 v1 < v2 (v2 較新)
    回傳 0  表示版本相同
    """
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    if p1 > p2:
        return 1
    elif p1 < p2:
        return -1
    return 0


def print_version(tool_name: str = "OpenLabOps Homelab Tools"):
    """印出統一格式之版本資訊"""
    ver = get_local_version()
    print(f"{tool_name} v{ver}")


if __name__ == "__main__":
    loc = get_local_version()
    rem = get_remote_version()
    print(f"本地版本: v{loc}")
    print(f"遠端版本: v{rem if rem else '無法連線'}")
    if rem:
        cmp = compare_versions(loc, rem)
        if cmp < 0:
            print(f"⚠️ 發現新版本 v{rem}，建議執行更新。")
        else:
            print("✅ 目前已是最新版本。")
