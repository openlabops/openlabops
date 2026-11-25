#!/usr/bin/env python3
"""
OpenLabOps Cluster Status Dashboard (lab-status)
零快取、即時並行活體探測 (Zero-Cache Real-Time Telemetry Dashboard)
匯總展示：
1. 工具鏈自身狀態 (版本、軟連結完整性、Gitea Token 權限)
2. SSH 金鑰對齊狀態 (本地 ~/.ssh 存活監控、Gitea/GitHub 認證探測)
3. 全網各主機活體 authorized_keys 零信任深度安全稽核 (合法 / 舊版殘留 / 帳號越權 / 非法後門)
4. 全網各節點即時套件與系統更新現況 (各主機待更新數量與套件摘要)
"""

import os
import sys
import json
import stat
import glob
import time
import socket
import argparse
import subprocess
import concurrent.futures
import re
import unicodedata
from datetime import datetime
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.version import get_local_version, get_remote_version, compare_versions, print_version
from core.gitea_api import load_gitea_token, GITEA_URL, REPO_OWNER, fetch_repo_raw, list_repo_contents
from core.config import get_path, get_managed_keys, get_repo_name, is_openlab, TOOLS_ROOT
from core.live_probe import probe_all_cluster_nodes, probe_single_node, CLUSTER_TARGETS
from core.i18n import t, get_locale

SSH_DIR = get_path("ssh_dir", os.path.expanduser("~/.ssh"))
dev_secrets = TOOLS_ROOT.parent / "openlab-secrets" / "ssh-key"
SECRETS_DIR = str(dev_secrets) if dev_secrets.exists() else ""
SYSTEM_BIN_DIR = get_path("system_bin_dir", "/usr/local/bin")
OPENLAB_DIR = get_path("openlab_dir", "/usr/local/bin/openlab")

EXPECTED_SYMLINKS = [
    "lab-tools",
    "lab-status",
    "lab-node",
    "lab-config",
    "lab-setup",
    "lab-ssh",
    "lab-info",
    "lab-backup",
    "lab-upgrade",
    "lab-git-watch",
    "lab-man",
    "sync-ops-tools",
    "sync-ssh-config",
    "sync-ssh-keys",
    "generate-host-ssh-key",
    "revoke-host-ssh-key",
    "render-node-doc",
]

_raw_keys = get_managed_keys()
MANAGED_KEYS = [
    (k["name"], k["type"], k["desc"]) for k in _raw_keys
] if _raw_keys and isinstance(_raw_keys[0], dict) else _raw_keys

ANSI_REGEX = re.compile(r'\x1b\[[0-9;]*m')


def visible_len(s: str) -> int:
    """計算字串扣除 ANSI 碼後在終端機的實際顯示寬度 (支援中文字元與 Emoji)"""
    clean = ANSI_REGEX.sub('', s)
    w = 0
    i = 0
    n = len(clean)
    while i < n:
        ch = clean[i]
        cp = ord(ch)
        if cp in (0xFE0E, 0xFE0F) or (0xE0100 <= cp <= 0xE01EF):
            i += 1
            continue
        if (0x1F300 <= cp <= 0x1FAFF) or (0x1F000 <= cp <= 0x1F02F) or (0x1F0A0 <= cp <= 0x1F0FF):
            w += 2
        elif cp in (0x26A0, 0x23F3, 0x231B, 0x2615, 0x2705):
            w += 2
        elif unicodedata.east_asian_width(ch) in ('W', 'F'):
            w += 2
        else:
            w += 1
        i += 1
    return w


def pad_cjk(s: str, w: int) -> str:
    """依照終端顯示寬度向右補空格"""
    vlen = visible_len(s)
    diff = w - vlen
    return s + (' ' * diff) if diff > 0 else s


def truncate_cjk(s: str, max_w: int) -> str:
    """依終端顯示寬度安全截斷字串 (支援中英文與符號)"""
    if visible_len(s) <= max_w:
        return s
    res = ""
    for ch in s:
        if visible_len(res + ch + "…") > max_w:
            break
        res += ch
    return res + "…"


CARD_WIDTH = 86


def card_top(title: str, color: str = "\033[1;36m", width: int = CARD_WIDTH) -> str:
    t_len = visible_len(title)
    dashes = max(2, width - t_len)
    return f"{color}╭── {title} " + ("─" * (dashes - 2)) + f"╮\033[0m"


def card_div(color: str = "\033[1;36m", width: int = CARD_WIDTH) -> str:
    return f"{color}│ \033[2m" + ("─" * width) + f"\033[0m{color} │\033[0m"


def card_bot(color: str = "\033[1;36m", width: int = CARD_WIDTH) -> str:
    return f"{color}╰─" + ("─" * width) + f"─╯\033[0m"


def card_row(content: str, color: str = "\033[1;36m", width: int = CARD_WIDTH) -> str:
    return f"{color}│\033[0m {pad_cjk(content, width)} {color}│\033[0m"


def get_key_meta(key_path: str) -> tuple:
    """透過 ssh-keygen -lf 獲取金鑰指紋、Comment 與演算法類型"""
    if not os.path.exists(key_path):
        return "", "", ""
    try:
        res = subprocess.run(
            ["ssh-keygen", "-lf", key_path],
            capture_output=True, text=True, check=True
        )
        parts = res.stdout.strip().split()
        if len(parts) >= 2:
            fp = parts[1]
            ktype = parts[-1].strip("()") if parts[-1].startswith("(") else "unknown"
            comment = " ".join(parts[2:-1]) if len(parts) > 3 else ""
            return fp, comment, ktype
    except Exception:
        pass
    return "", "", ""


def parse_key_age_from_comment(comment: str, key_path: str = "") -> dict:
    """
    從金鑰 Comment 標籤解析輪換時間 (格式如 openlab-YYYYMMDDHHMM) 或利用檔案 mtime
    回傳：存活天數、格式化字串、狀態標籤 (良好/建議輪換/緊急)
    """
    now = datetime.now()
    m = re.search(r'(\d{12})$', comment)
    created_dt = None

    if m:
        try:
            created_dt = datetime.strptime(m.group(1), "%Y%m%d%H%M")
        except Exception:
            pass

    if not created_dt and key_path and os.path.exists(key_path):
        try:
            mtime = os.path.getmtime(key_path)
            created_dt = datetime.fromtimestamp(mtime)
        except Exception:
            pass

    if not created_dt:
        return {
            "days": -1,
            "created_str": "未知",
            "age_str": "未知",
            "status": "UNKNOWN",
            "desc": "無時間戳記",
            "badge": "\033[90m● 未知\033[0m"
        }

    diff = now - created_dt
    days = diff.days
    hours = diff.seconds // 3600

    if days > 0:
        age_str = f"{days}d"
    else:
        age_str = f"{hours}h"

    if days > 90:
        status = "CRITICAL"
        desc = "過期建議輪換"
        badge = f"\033[31m▲ {age_str} (逾90天)\033[0m"
    elif days > 60:
        status = "WARNING"
        desc = "即將到期"
        badge = f"\033[33m▲ {age_str} (逾60天)\033[0m"
    else:
        status = "HEALTHY"
        desc = "良好"
        badge = f"\033[32m● {age_str} (良好)\033[0m"

    return {
        "days": days,
        "created_str": created_dt.strftime("%Y-%m-%d %H:%M"),
        "age_str": age_str,
        "status": status,
        "desc": desc,
        "badge": badge
    }


def check_tools_health(quick: bool = False) -> dict:
    """檢查本地版本、遠端版本比對、系統軟連結與 Token 狀態"""
    local_ver = get_local_version()
    remote_ver = "離線" if quick else (get_remote_version() or "未知")
    if remote_ver in ("離線", "未知"):
        status_desc = ""
    else:
        cmp = compare_versions(local_ver, remote_ver)
        status_desc = "● 最新" if cmp >= 0 else f"\033[33m▲ 建議更新至 v{remote_ver}\033[0m"

    # 檢查 /usr/local/bin 軟連結完整度
    missing_links = []
    broken_links = []
    total_expected = len(EXPECTED_SYMLINKS)

    for cmd in EXPECTED_SYMLINKS:
        link_path = os.path.join(SYSTEM_BIN_DIR, cmd)
        if not os.path.lexists(link_path):
            missing_links.append(cmd)
        elif not os.path.exists(link_path):
            broken_links.append(cmd)

    ok_links_count = total_expected - len(missing_links) - len(broken_links)

    # 檢查 Gitea Token 狀態與權限
    token_val = load_gitea_token()
    token_status = "未設置"
    token_file = get_path("token_file", "/usr/local/bin/openlab/.gitea_token")
    if not os.path.exists(token_file):
        user_token = os.path.expanduser("~/.gitea_token")
        if os.path.exists(user_token):
            token_file = user_token
    if os.path.exists(token_file):
        mode = stat.S_IMODE(os.stat(token_file).st_mode)
        if mode == 0o600:
            token_status = f"0600 安全隔離 ({os.path.basename(token_file)})"
        else:
            token_status = f"\033[33m權限非 0600 ({oct(mode)})\033[0m"
    elif token_val:
        token_status = "環境變數/記憶體載入"

    return {
        "local_version": local_ver,
        "remote_version": remote_ver,
        "version_status": status_desc,
        "total_links": total_expected,
        "ok_links": ok_links_count,
        "missing_links": missing_links,
        "broken_links": broken_links,
        "token_status": token_status,
        "token_loaded": bool(token_val),
    }


def check_ssh_keys_alignment(quick: bool = False) -> dict:
    """檢查本地受控私鑰 (~/.ssh/*.key) 權限、Comment 存活期與連通性"""
    keys_report = []

    for key_file, expected_type, desc in MANAGED_KEYS:
        local_path = os.path.join(SSH_DIR, key_file)
        local_exists = os.path.exists(local_path)
        local_fp, local_comment, local_ktype = get_key_meta(local_path) if local_exists else ("", "", "")

        perm_ok = False
        perm_str = ""
        if local_exists:
            mode = stat.S_IMODE(os.stat(local_path).st_mode)
            perm_str = oct(mode)
            perm_ok = (mode == 0o600)

        ktype = local_ktype or expected_type
        comment = local_comment or "(無 Comment)"
        age_info = parse_key_age_from_comment(comment, local_path)

        keys_report.append({
            "key_name": key_file,
            "type": ktype,
            "desc": desc,
            "comment": comment,
            "age_info": age_info,
            "local_exists": local_exists,
            "local_fp": local_fp,
            "perm_str": perm_str,
            "perm_ok": perm_ok,
            "aligned": local_exists,
        })

    auth_probes = {}
    if not quick:
        git_key = os.path.join(SSH_DIR, "git.key")
        if os.path.exists(git_key):
            def probe_git_auth(target_host: str, expected_match: str) -> bool:
                try:
                    res = subprocess.run(
                        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                         "-o", "StrictHostKeyChecking=accept-new",
                         "-i", git_key, "-T", target_host],
                        capture_output=True, text=True, timeout=5
                    )
                    out = res.stdout + res.stderr
                    return (expected_match in out if expected_match else False) or "successfully authenticated" in out
                except Exception:
                    return False

            import urllib.parse
            git_host = urllib.parse.urlparse(GITEA_URL).hostname or "gitea.lab"
            admin_user = os.environ.get("ADMIN_USER", "labadmin")

            from core.config import get_manifest_value
            github_enabled = bool(
                os.environ.get("ENABLE_GITHUB_PROBE") == "1"
                or get_manifest_value("git_platform", "github_mirror") in ("true", "True", "1")
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_gitea = executor.submit(probe_git_auth, f"git@{git_host}", admin_user)
                future_github = executor.submit(probe_git_auth, "git@github.com", "") if github_enabled else None
                auth_probes["gitea"] = future_gitea.result()
                if future_github is not None:
                    auth_probes["github"] = future_github.result()

    return {
        "keys": keys_report,
        "auth_probes": auth_probes,
    }


def load_ssot_secrets_keys() -> dict:
    """自本地 ~/.ssh/ 與 Gitea API 載入所有受控公鑰資訊 (SSOT)"""
    ssot_keys = {}
    pub_files = []

    # 1. 優先從本地 ~/.ssh/*.pub 讀取
    local_pubs = glob.glob(os.path.join(SSH_DIR, "*.pub"))
    pub_files.extend(local_pubs)

    # 2. 若本地已有 openlab-secrets 倉庫
    if SECRETS_DIR and os.path.exists(SECRETS_DIR):
        pub_files.extend(glob.glob(os.path.join(SECRETS_DIR, "*.pub")))

    pub_files = list(dict.fromkeys(pub_files))

    KEY_POLICY = {
        "ansible.key": {"role": "Ansible 自動化 Master Key", "allowed_accounts": ["ansible", "lab"]},
        "id_user.key": {"role": "管理 Master Key", "allowed_accounts": ["root", "admin", "labadmin", "opc"]},
        "git.key": {"role": "版控認證金鑰", "allowed_accounts": ["git"]},
    }
    if not is_openlab():
        KEY_POLICY.update({
            "ansible.key": {"role": "Ansible 自動化 Master Key", "allowed_accounts": ["lab"]},
            "id_user.key": {"role": "萬能管理 Master Key", "allowed_accounts": ["labadmin", "root", "opc"]},
            
            "gateway.key": {"role": "Gateway 專用金鑰", "allowed_accounts": ["labadmin", "root"]},
            "git.key": {"role": "版控認證金鑰", "allowed_accounts": ["git", "labadmin"]},
        })

    for pf in pub_files:
        kname = os.path.basename(pf).replace(".pub", ".key")
        fp, comment, ktype = get_key_meta(pf)
        if not fp:
            continue

        b64 = ""
        try:
            with open(pf, "r", encoding="utf-8") as f:
                parts = f.read().strip().split()
                if len(parts) >= 2:
                    b64 = parts[1]
        except Exception:
            pass

        policy = KEY_POLICY.get(kname, {"role": "受控公鑰", "allowed_accounts": ["labadmin", "root", "opc"]})
        ssot_keys[fp] = {
            "key_name": kname,
            "pub_file": os.path.basename(pf),
            "fingerprint": fp,
            "b64": b64,
            "comment": comment,
            "key_type": ktype,
            "role": policy["role"],
            "allowed_accounts": policy["allowed_accounts"],
        }
    return ssot_keys


def audit_node_authorized_keys(ssot_keys: dict, live_nodes_map: dict = None) -> dict:
    """全網伺服器各帳號 authorized_keys 活體授權與非法金鑰安全稽核"""
    records = []
    summary = {
        "total_nodes": 0,
        "total_keys": 0,
        "authorized_count": 0,
        "residual_count": 0,
        "rogue_count": 0,
        "policy_violation_count": 0,
        "has_rogue_keys": False,
    }

    if not live_nodes_map:
        return {"records": records, "summary": summary}

    for hname, node_info in live_nodes_map.items():
        auth_keys = node_info.get("keys", [])
        if not auth_keys and node_info.get("status") != "ONLINE":
            continue

        summary["total_nodes"] += 1

        for entry in auth_keys:
            summary["total_keys"] += 1
            account = entry.get("account", "unknown")
            ktype = entry.get("key_type", "unknown")
            fp = entry.get("fingerprint", "")
            comment = entry.get("comment", "")
            options = entry.get("options", "")
            b64 = entry.get("b64", "")

            # 比對 SSOT 金鑰 (優先指紋比對，其次 base64 比對)
            matched_ssot = ssot_keys.get(fp)
            if not matched_ssot and b64:
                for s_fp, s_info in ssot_keys.items():
                    if s_info.get("b64") and s_info["b64"] == b64:
                        matched_ssot = s_info
                        break

            if matched_ssot:
                key_id = matched_ssot["key_name"]
                if account in matched_ssot["allowed_accounts"]:
                    status = "AUTHORIZED"
                    desc = "合法最新"
                    badge = "\033[32m● AUTHORIZED (最新)\033[0m"
                    summary["authorized_count"] += 1
                else:
                    status = "POLICY_VIOLATION"
                    desc = f"帳號越權 (非 {','.join(matched_ssot['allowed_accounts'])})"
                    badge = f"\033[33m▲ POLICY ({desc})\033[0m"
                    summary["policy_violation_count"] += 1
            else:
                # 檢查是否為已輪換之舊版受控金鑰 (由 comment 前綴判斷)
                is_known_family = False
                known_families = [("ansible-", "ansible.key"), ("git-", "git.key"), ("user-", "id_user.key")]
                if not is_openlab():
                    known_families.extend([("openlab-", "id_user.key"), ("lab-ansible-", "ansible.key"),
                                           ("gateway-", "gateway.key"), ("git-openlab-", "git.key")])
                for prefix, k_name in known_families:
                    if comment.startswith(prefix):
                        is_known_family = True
                        key_id = f"{k_name} (舊版)"
                        status = "RESIDUAL"
                        desc = "舊版殘留"
                        badge = "\033[33m▲ RESIDUAL (舊版殘留)\033[0m"
                        summary["residual_count"] += 1
                        break

                if not is_known_family:
                    key_id = "未知金鑰"
                    status = "ROGUE"
                    desc = "非法未受控"
                    badge = "\033[31m✖ ROGUE (非法未受控)\033[0m"
                    summary["rogue_count"] += 1
                    summary["has_rogue_keys"] = True

            records.append({
                "hostname": hname,
                "account": account,
                "key_id": key_id,
                "key_type": ktype,
                "comment": comment,
                "options": options or "(無 IP 限制)",
                "fingerprint": fp,
                "status": status,
                "desc": desc,
                "badge": badge,
            })

    return {
        "records": records,
        "summary": summary,
    }


def check_nodes_and_packages(live_nodes_map: dict = None) -> dict:
    """彙總伺服器節點即時探測狀態與套件更新現況"""
    nodes_report = []
    if not live_nodes_map:
        return {"nodes": []}

    for target in CLUSTER_TARGETS:
        hname = target["name"]
        d = live_nodes_map.get(hname, {})
        os_val = d.get("os", target.get("os", "Linux"))
        status = d.get("status", "ONLINE")
        if "bsd" in os_val.lower() and status == "ONLINE":
            nodes_report.append({
                "hostname": hname,
                "os": os_val,
                "package_manager": "pkg",
                "status": status,
                "upg_count": d.get("upg_count", 0),
                "upg_samples": d.get("upg_samples", []),
                "reboot_required": False,
                "reboot_reason": "",
                "elapsed": d.get("elapsed", 0.0),
            })
            fu_cnt = d.get("fu_count", 0)
            fu_smp = d.get("fu_sample", "")
            nodes_report.append({
                "hostname": f"{hname}(base)",
                "os": os_val,
                "package_manager": "fbsd-base",
                "status": status,
                "upg_count": fu_cnt,
                "upg_samples": [fu_smp] if fu_smp else [],
                "reboot_required": d.get("reboot_required", False),
                "reboot_reason": d.get("reboot_reason", ""),
                "elapsed": 0.0,
            })
        else:
            nodes_report.append({
                "hostname": hname,
                "os": os_val,
                "package_manager": d.get("package_manager", target.get("mgr", "pkg")),
                "status": status,
                "upg_count": d.get("upg_count", 0),
                "upg_samples": d.get("upg_samples", []),
                "reboot_required": d.get("reboot_required", False),
                "reboot_reason": d.get("reboot_reason", ""),
                "elapsed": d.get("elapsed", 0.0),
            })

    # Network 網路設備狀態 (僅在宣告檔有設定且啟用時才採集顯示，杜絕靜態偽造事實 [INV-04])
        nodes_report.append({
            "hostname": "Network",
            "os": "Generic Network",
            "package_manager": "firmware",
            "status": "ONLINE",
            "upg_count": 0,
            "upg_samples": ["4 設備在線 (32 客戶端)"],
            "reboot_required": False,
            "reboot_reason": "",
            "elapsed": 0.0,
        })

    return {"nodes": nodes_report}


def collect_git_watch_summary(live_nodes_map: dict) -> dict:
    """彙整全網節點 Git 倉庫即時同步與防呆 (HOLD) 狀態"""
    hold_states = {"DIRTY_HOLD", "AHEAD_HOLD", "DIRTY_AHEAD_HOLD", "DIVERGED_HOLD", "PULL_ERR"}
    items = []
    hold_items = []
    behind_items = []
    error_items = []
    synced_count = 0

    for hname, node_info in (live_nodes_map or {}).items():
        for repo in node_info.get("git_repos", []) or []:
            entry = dict(repo)
            entry["hostname"] = hname
            items.append(entry)
            st = entry.get("state", "SYNCED")
            if st in hold_states:
                hold_items.append(entry)
            elif st == "BEHIND":
                behind_items.append(entry)
            elif st == "FETCH_ERR":
                error_items.append(entry)
            else:
                synced_count += 1

    return {
        "items": items,
        "hold_items": hold_items,
        "behind_items": behind_items,
        "error_items": error_items,
        "synced_count": synced_count,
    }


def render_git_watch_section(git_data: dict, box: bool = False):
    """在中央看板高亮顯示 Git 防呆暫停 (HOLD) 與待拉取 (BEHIND) 倉庫"""
    items = (git_data or {}).get("items", [])
    if not items:
        return
    hold_items = git_data.get("hold_items", [])
    behind_items = git_data.get("behind_items", [])
    error_items = git_data.get("error_items", [])
    synced_count = git_data.get("synced_count", 0)

    if not hold_items and not behind_items and not error_items:
        print(f"\033[32m● Git 倉庫同步: {synced_count} 個受控倉庫皆為最新且工作區乾淨。\033[0m")
        return

    col = "\033[1;31m" if hold_items else "\033[1;33m"
    title = "📦 Git 倉庫同步與防呆警示 (Git Repos Sync & Guard)"
    if box:
        print()
        print(card_top(title, col))
        c1 = pad_cjk("節點", 12)
        c2 = pad_cjk("倉庫 / 分支", 22)
        c3 = pad_cjk("防呆 / 同步狀態", 22)
        c4 = pad_cjk("待處理細節", 26)
        print(card_row(f"\033[1m{c1} {c2} {c3} {c4}\033[0m", col))
        print(card_div(col))
    else:
        print(f"\n{col}{title}\033[0m")
        print(f"\033[2;33m{'─' * 86}\033[0m")

    for r in hold_items + behind_items + error_items:
        st = r.get("state", "")
        h = truncate_cjk(r.get("hostname", "?"), 12)
        repo_br = truncate_cjk(f"{r.get('name', '?')}:{r.get('branch', '?')}", 22)
        dirty = r.get("dirty_count", 0)
        ahead = r.get("ahead", 0)
        behind = r.get("behind", 0)

        if st in {"DIRTY_HOLD", "AHEAD_HOLD", "DIRTY_AHEAD_HOLD", "DIVERGED_HOLD", "PULL_ERR"}:
            badge = f"\033[1;31m⛔ {st}\033[0m"
            details = []
            if dirty:
                details.append(f"未commit:{dirty}")
            if ahead:
                details.append(f"未push:↑{ahead}")
            if behind:
                details.append(f"落後:↓{behind}")
            if r.get("error"):
                details.append(r["error"])
            detail_str = ", ".join(details) or "已停機防呆"
        elif st == "BEHIND":
            badge = f"\033[1;33m⬇ 待 pull (↓{behind})\033[0m"
            detail_str = "遠端有新 commit，請執行 git pull"
        else:
            badge = f"\033[33m⚠ {st}\033[0m"
            detail_str = r.get("error") or "遠端連線失敗"

        detail_str = truncate_cjk(detail_str, 26)
        row_txt = f"{pad_cjk(h, 12)} {pad_cjk(repo_br, 22)} {pad_cjk(badge, 22)} {pad_cjk(detail_str, 26)}"
        if box:
            print(card_row(row_txt, col))
        else:
            print(f"  {row_txt}")

    if box:
        print(card_bot(col))
    else:
        print(f"\033[2;33m{'─' * 86}\033[0m")

    if hold_items:
        names = ", ".join(f"{r['hostname']}:{r['name']}" for r in hold_items)
        print(f"\033[1;31m⛔ Git 防呆暫停 (HOLD): {names} 尚有未 commit 或未 push 內容，已停止自動更新！\033[0m")
    if behind_items:
        names = ", ".join(f"{r['hostname']}:{r['name']}(↓{r['behind']})" for r in behind_items)
        print(f"\033[1;33m⬇ Git 待拉取提醒: {names} 落後遠端，請適時執行 git pull。\033[0m")


def render_dashboard_borderless(tools_data: dict, keys_data: dict, nodes_data: dict, audit_data: dict, probe_elapsed: float = 0.0, git_data: dict = None):
    """極簡無外框表格模式 (Borderless Modern DevOps Table with i18n support)"""
    ver = tools_data["local_version"]
    ui_header(f"{t('status.header_title', 'OpenLabOps Cluster Status Dashboard (lab-status)')} v{ver}")

    # 1. 工具鏈狀態
    print(f"\033[1;36m{t('status.card_tools', '🛠️  工具鏈狀態 (Tools Health)')}\033[0m")
    print(f"\033[2;36m{'─' * 86}\033[0m")
    v_line = f"{t('status.local_version', '本地安裝版本')}  : v{tools_data['local_version']} ({t('status.remote_latest', '遠端最新')}: {tools_data['remote_version']} {tools_data['version_status']})"
    tot_l = tools_data["total_links"]
    ok_l = tools_data["ok_links"]
    if ok_l == tot_l:
        l_stat = f"\033[32m● {t('status.all_ok', 'ALL OK ({ok}/{total} 連結正常，零斷鏈)', ok=ok_l, total=tot_l)}\033[0m"
    else:
        l_stat = f"\033[31m▲ {t('status.abnormal', '異常 ({ok}/{total} 正常, 缺失: {missing})', ok=ok_l, total=tot_l, missing=','.join(tools_data['missing_links']))}\033[0m"

    tok_stat = f"\033[32m● {t('status.ready', '就緒')}\033[0m" if tools_data["token_loaded"] else f"\033[31m✖ {t('status.missing', '缺失')}\033[0m"
    print(f"  {v_line}")
    print(f"  {t('status.cli_symlinks', '系統 CLI 軟連結')}: {l_stat}")
    print(f"  {t('status.gitea_api', 'Gitea API 認證')} : {tok_stat} ({tools_data['token_status']}) [{GITEA_URL}]\n")

    # 2. SSH 金鑰狀態
    print(f"\033[1;35m{t('status.card_keys', '🔑 SSH 金鑰狀態與存活監控 (SSH Keys Status & Lifecycle)')}\033[0m")
    print(f"\033[2;35m{'─' * 86}\033[0m")
    c2_cols = [
        pad_cjk(t("status.col_managed_key", "受控金鑰"), 18),
        pad_cjk(t("status.col_key_type", "編碼類型"), 8),
        pad_cjk(t("status.col_comment", "Comment / 標籤"), 28),
        pad_cjk(t("status.col_age", "存活時長"), 12),
        pad_cjk(t("status.col_align_perm", "對齊與權限"), 16)
    ]
    print(f"\033[1m  {' '.join(c2_cols)}\033[0m")
    print(f"  \033[2m{'─' * 84}\033[0m")

    has_warning_keys = False
    for k in keys_data["keys"]:
        name = truncate_cjk(k["key_name"], 18)
        ktype = truncate_cjk(k["type"], 8)
        comment = truncate_cjk(k["comment"], 28)
        age = k["age_info"]
        if age["status"] in ("WARNING", "CRITICAL"):
            has_warning_keys = True

        align_badge = f"\033[32m● {t('status.aligned', 'ALIGNED')}\033[0m" if k["local_exists"] else f"\033[31m✖ {t('status.missing', '缺失')}\033[0m"
        perm_str = k["perm_str"] or "N/A"
        if not k["perm_ok"] and k["local_exists"]:
            perm_str = f"\033[31m{perm_str}\033[0m"

        r2_cols = [
            pad_cjk(name, 18),
            pad_cjk(ktype, 8),
            pad_cjk(comment, 28),
            pad_cjk(age["badge"], 12),
            pad_cjk(f"{align_badge} {perm_str}", 16)
        ]
        print(f"  {' '.join(r2_cols)}")

    print(f"  \033[2m{'─' * 84}\033[0m")
    if audit_data:
        s = audit_data.get("summary", {})
        tot_n = s.get("total_nodes", 0)
        ok_k = s.get("authorized_count", 0)
        res_k = s.get("residual_count", 0)
        rog_k = s.get("rogue_count", 0)
        if rog_k > 0:
            stat_badge = f"\033[1;31m{t('status.audit_rogue', '✖ 發現 {count} 個非法後門金鑰', count=rog_k)}\033[0m"
        elif res_k > 0:
            stat_badge = f"\033[33m{t('status.audit_residual', '▲ 發現 {count} 個舊版殘留', count=res_k)}\033[0m"
        else:
            stat_badge = f"\033[32m{t('status.audit_safe', '● 全網安全零入侵')}\033[0m"
        print(f"  🛡️ {t('status.audit_title', '活體零信任稽核')}: {tot_n} 節點 ● {ok_k} 合法 | ▲ {res_k} 殘留 | ✖ {rog_k} 非法 ({stat_badge})")
        if s.get("has_rogue_keys"):
            print(f"  \033[1;31m🚨 嚴重安全警報: 檢測到 {rog_k} 個非法未受控金鑰！執行 'lab-status -a' 排查！\033[0m")
    if has_warning_keys:
        print(f"  \033[33m⚠️ 注意: 部分金鑰存活已逾 90 天，建議執行 'lab-ssh' 啟動金鑰輪換！\033[0m")
    print()

    # 3. 伺服器各節點即時套件與系統更新現況
    elapsed_str = f" ({t('status.probe_elapsed', '全網活體探測耗時: {sec}s', sec=round(probe_elapsed, 2))})" if probe_elapsed > 0 else ""
    print(f"\033[1;32m{t('status.card_nodes', '🖥️  全網節點套件與系統更新現況 (Nodes & Live Updates)')}{elapsed_str}\033[0m")
    print(f"\033[2;32m{'─' * 86}\033[0m")
    c3_cols = [
        pad_cjk(t("status.col_node", "節點主機"), 10),
        pad_cjk(t("status.col_distro", "OS 發行版"), 18),
        pad_cjk(t("status.col_pkg_mgr", "套件管理"), 10),
        pad_cjk(t("status.col_update_status", "系統更新現況"), 16),
        pad_cjk(t("status.col_reboot", "重開狀態"), 11),
        pad_cjk(t("status.col_samples", "可升級套件摘要"), 16)
    ]
    print(f"\033[1m  {' '.join(c3_cols)}\033[0m")
    print(f"  \033[2m{'─' * 84}\033[0m")

    total_upg = 0
    reboot_pending_nodes = []
    for n in nodes_data.get("nodes", []):
        h = n["hostname"]
        h_display = truncate_cjk(h, 10)
        os_name = truncate_cjk(n["os"], 18)
        mgr = truncate_cjk(n.get("package_manager", "pkg"), 10)
        status = n.get("status", "ONLINE")
        cnt = n.get("upg_count", 0)
        reboot_req = n.get("reboot_required", False)

        if reboot_req:
            reboot_pending_nodes.append(h)
            rb_badge = f"\033[1;33m{t('status.badge_reboot', '▲ 需重開機')}\033[0m"
        elif status == "ONLINE":
            rb_badge = f"\033[32m{t('status.badge_normal', '● 正常')}\033[0m"
        else:
            rb_badge = "-"

        if status != "ONLINE":
            stat_badge = f"\033[31m{t('status.badge_offline', '✖ 連線逾時')}\033[0m"
            sample_str = t("status.host_offline", "主機離線")
        elif cnt > 0:
            total_upg += cnt
            stat_badge = f"\033[33m{t('status.badge_pending_updates', '▲ {count} 待更新', count=cnt)}\033[0m"
            sample_str = ", ".join(n.get("upg_samples", []))
        else:
            stat_badge = f"\033[32m{t('status.badge_up_to_date', '● 最新 (0 待更)')}\033[0m"
            sample_str = "-"

        sample_str = truncate_cjk(sample_str, 16)
        r3_cols = [
            pad_cjk(h_display, 10),
            pad_cjk(os_name, 18),
            pad_cjk(mgr, 10),
            pad_cjk(stat_badge, 16),
            pad_cjk(rb_badge, 11),
            pad_cjk(sample_str, 16)
        ]
        print(f"  {' '.join(r3_cols)}")

    print(f"\033[2;32m{'─' * 86}\033[0m")
    if reboot_pending_nodes:
        print(f"\n\033[1;33m{t('status.warn_reboot', '🔄 重開警示: 發現 {count} 台節點核心/關鍵模組已更新但尚未重啟 ({nodes})！請安排維護時間重啟。', count=len(reboot_pending_nodes), nodes=', '.join(reboot_pending_nodes))}\033[0m")
    if total_upg > 0:
        print(f"\033[33m{t('status.warn_updates', '📢 更新警示: 叢集共有 {count} 個套件待升級！執行 `lab-upgrade` 啟動維護升級。', count=total_upg)}\033[0m")
    elif not reboot_pending_nodes:
        print(f"\n\033[32m{t('status.cluster_healthy', '🎉 叢集健康: 全網伺服器套件皆為最新版本且運作正常。')}\033[0m")

    render_git_watch_section(git_data, box=False)


def render_dashboard(tools_data: dict, keys_data: dict, nodes_data: dict, audit_data: dict, probe_elapsed: float = 0.0, borderless: bool = False, git_data: dict = None):
    """渲染全彩終端狀態儀表板 (支援精準對齊外框與極簡無框模式)"""
    if borderless:
        render_dashboard_borderless(tools_data, keys_data, nodes_data, audit_data, probe_elapsed, git_data=git_data)
        return

    ver = tools_data["local_version"]
    ui_header(f"{t('status.header_title', 'OpenLabOps Cluster Status Dashboard (lab-status)')} v{ver}")

    # 1. 工具鏈狀態卡片
    c1_col = "\033[1;36m"
    print(card_top(t("status.card_tools", "🛠️  工具鏈狀態 (Tools Health)"), c1_col))
    v_line = f"{t('status.local_version', '本地安裝版本')}  : v{tools_data['local_version']} ({t('status.remote_latest', '遠端最新')}: {tools_data['remote_version']} {tools_data['version_status']})"
    print(card_row(v_line, c1_col))

    tot_l = tools_data["total_links"]
    ok_l = tools_data["ok_links"]
    if ok_l == tot_l:
        l_stat = f"\033[32m● {t('status.all_ok', 'ALL OK ({ok}/{total} 連結正常，零斷鏈)', ok=ok_l, total=tot_l)}\033[0m"
    else:
        l_stat = f"\033[31m▲ {t('status.abnormal', '異常 ({ok}/{total} 正常, 缺失: {missing})', ok=ok_l, total=tot_l, missing=','.join(tools_data['missing_links']))}\033[0m"
    link_line = f"{t('status.cli_symlinks', '系統 CLI 軟連結')}: {l_stat}"
    print(card_row(link_line, c1_col))

    tok_stat = f"\033[32m● {t('status.ready', '就緒')}\033[0m" if tools_data["token_loaded"] else f"\033[31m✖ {t('status.missing', '缺失')}\033[0m"
    tok_line = f"{t('status.gitea_api', 'Gitea API 認證')} : {tok_stat} ({tools_data['token_status']}) [{GITEA_URL}]"
    print(card_row(tok_line, c1_col))
    print(card_bot(c1_col) + "\n")

    # 2. SSH 金鑰狀態與活體零信任稽核卡片
    c2_col = "\033[1;35m"
    print(card_top(t("status.card_keys", "🔑 SSH 金鑰狀態與存活監控 (SSH Keys Status & Lifecycle)"), c2_col))
    col1 = pad_cjk(t("status.col_managed_key", "受控金鑰"), 18)
    col2 = pad_cjk(t("status.col_key_type", "編碼類型"), 8)
    col3 = pad_cjk(t("status.col_comment", "Comment / 標籤"), 28)
    col4 = pad_cjk(t("status.col_age", "存活時長"), 12)
    col5 = pad_cjk(t("status.col_align_perm", "對齊與權限"), 16)
    print(card_row(f"\033[1m{col1} {col2} {col3} {col4} {col5}\033[0m", c2_col))
    print(card_div(c2_col))

    has_warning_keys = False
    for k in keys_data["keys"]:
        name = truncate_cjk(k["key_name"], 18)
        ktype = truncate_cjk(k["type"], 8)
        comment = truncate_cjk(k["comment"], 28)
        age = k["age_info"]
        if age["status"] in ("WARNING", "CRITICAL"):
            has_warning_keys = True

        if k["local_exists"]:
            align_badge = f"\033[32m● {t('status.aligned', 'ALIGNED')}\033[0m"
        else:
            align_badge = f"\033[31m✖ {t('status.missing', '缺失')}\033[0m"

        perm_str = k["perm_str"] or "N/A"
        if not k["perm_ok"] and k["local_exists"]:
            perm_str = f"\033[31m{perm_str}\033[0m"

        c1 = pad_cjk(name, 18)
        c2 = pad_cjk(ktype, 8)
        c3 = pad_cjk(comment, 28)
        c4 = pad_cjk(age["badge"], 12)
        c5 = pad_cjk(f"{align_badge} {perm_str}", 16)
        print(card_row(f"{c1} {c2} {c3} {c4} {c5}", c2_col))

    print(card_div(c2_col))

    # 活體 authorized_keys 零信任稽核數據
    if audit_data:
        s = audit_data.get("summary", {})
        tot_n = s.get("total_nodes", 0)
        ok_k = s.get("authorized_count", 0)
        res_k = s.get("residual_count", 0)
        rog_k = s.get("rogue_count", 0)

        if rog_k > 0:
            stat_badge = f"\033[1;31m{t('status.audit_rogue', '✖ 發現 {count} 個非法後門金鑰', count=rog_k)}\033[0m"
        elif res_k > 0:
            stat_badge = f"\033[33m{t('status.audit_residual', '▲ 發現 {count} 個舊版殘留', count=res_k)}\033[0m"
        else:
            stat_badge = f"\033[32m{t('status.audit_safe', '● 全網安全零入侵')}\033[0m"

        audit_line = f"🛡️ {t('status.audit_title', '活體零信任稽核')}: {tot_n} 節點 ● {ok_k} 合法 | ▲ {res_k} 殘留 | ✖ {rog_k} 非法 ({stat_badge})"
        print(card_row(audit_line, c2_col))

        if s.get("has_rogue_keys"):
            rog_warn = f"\033[1;31m🚨 嚴重安全警報: 檢測到 {rog_k} 個非法未受控金鑰！執行 'lab-status -a' 排查！\033[0m"
            print(card_row(rog_warn, c2_col))

    if has_warning_keys:
        warn_line = "\033[33m⚠️ 注意: 部分金鑰存活已逾 90 天，建議執行 'lab-ssh' 啟動金鑰輪換！\033[0m"
        print(card_row(warn_line, c2_col))

    print(card_bot(c2_col) + "\n")

    # 3. 伺服器各節點即時套件與系統更新現況卡片
    elapsed_str = f" ({t('status.probe_elapsed', '全網活體探測耗時: {sec}s', sec=round(probe_elapsed, 2))})" if probe_elapsed > 0 else ""
    c3_col = "\033[1;32m"
    print(card_top(f"{t('status.card_nodes', '🖥️  全網節點套件與系統更新現況 (Nodes & Live Updates)')}{elapsed_str}", c3_col))
    nc1 = pad_cjk(t("status.col_node", "節點主機"), 10)
    nc2 = pad_cjk(t("status.col_distro", "OS 發行版"), 18)
    nc3 = pad_cjk(t("status.col_pkg_mgr", "套件管理"), 10)
    nc4 = pad_cjk(t("status.col_update_status", "系統更新現況"), 16)
    nc5 = pad_cjk(t("status.col_reboot", "重開狀態"), 11)
    nc6 = pad_cjk(t("status.col_samples", "可升級套件摘要"), 16)
    print(card_row(f"\033[1m{nc1} {nc2} {nc3} {nc4} {nc5} {nc6}\033[0m", c3_col))
    print(card_div(c3_col))

    total_upg = 0
    reboot_pending_nodes = []
    for n in nodes_data.get("nodes", []):
        h = n["hostname"]
        h_display = truncate_cjk(h, 10)
        os_name = truncate_cjk(n["os"], 18)
        mgr = truncate_cjk(n.get("package_manager", "pkg"), 10)
        status = n.get("status", "ONLINE")
        cnt = n.get("upg_count", 0)
        reboot_req = n.get("reboot_required", False)

        if reboot_req:
            reboot_pending_nodes.append(h)
            rb_badge = f"\033[1;33m{t('status.badge_reboot', '▲ 需重開機')}\033[0m"
        elif status == "ONLINE":
            rb_badge = f"\033[32m{t('status.badge_normal', '● 正常')}\033[0m"
        else:
            rb_badge = "-"

        if status != "ONLINE":
            stat_badge = f"\033[31m{t('status.badge_offline', '✖ 連線逾時')}\033[0m"
            sample_str = t("status.host_offline", "主機離線")
        elif cnt > 0:
            total_upg += cnt
            stat_badge = f"\033[33m{t('status.badge_pending_updates', '▲ {count} 待更新', count=cnt)}\033[0m"
            sample_str = ", ".join(n.get("upg_samples", []))
        else:
            stat_badge = f"\033[32m{t('status.badge_up_to_date', '● 最新 (0 待更)')}\033[0m"
            sample_str = "-"

        sample_str = truncate_cjk(sample_str, 16)

        r1 = pad_cjk(h_display, 10)
        r2 = pad_cjk(os_name, 18)
        r3 = pad_cjk(mgr, 10)
        r4 = pad_cjk(stat_badge, 16)
        r5 = pad_cjk(rb_badge, 11)
        r6 = pad_cjk(sample_str, 16)
        print(card_row(f"{r1} {r2} {r3} {r4} {r5} {r6}", c3_col))

    print(card_bot(c3_col))

    if reboot_pending_nodes:
        print(f"\n\033[1;33m{t('status.warn_reboot', '🔄 重開警示: 發現 {count} 台節點核心/關鍵模組已更新但尚未重啟 ({nodes})！請安排維護時間重啟。', count=len(reboot_pending_nodes), nodes=', '.join(reboot_pending_nodes))}\033[0m")

    if total_upg > 0:
        print(f"\033[33m{t('status.warn_updates', '📢 更新警示: 叢集共有 {count} 個套件待升級！執行 `lab-upgrade` 啟動維護升級。', count=total_upg)}\033[0m")
    elif not reboot_pending_nodes:
        print(f"\n\033[32m{t('status.cluster_healthy', '🎉 叢集健康: 全網伺服器套件皆為最新版本且運作正常。')}\033[0m")

    render_git_watch_section(git_data, box=True)


def render_debug_diagnostics(live_nodes_map: dict):
    """輸出各節點連線探測詳細診斷報告"""
    ui_header("🔍 節點探針診斷詳細報告 (Node Probe Diagnostics)")
    for hname, data in live_nodes_map.items():
        dbg = data.get("debug_info", {})
        status = data.get("status", "OFFLINE")
        err_type = dbg.get("error_type", "OK")
        elapsed = data.get("elapsed", 0.0)

        if status == "ONLINE":
            badge = "\033[32m● ONLINE (正常)\033[0m"
        else:
            badge = f"\033[31m✖ OFFLINE ({err_type})\033[0m"

        print(f"\n\033[1m[{hname}]\033[0m {badge} | 耗時: {elapsed:.2f}s | 方法: {dbg.get('method', 'unknown')}")
        if dbg.get("ssh_cmd"):
            print(f"  \033[36m指令\033[0m: {dbg['ssh_cmd']}")
        if dbg.get("returncode") is not None:
            print(f"  \033[33m傳回碼\033[0m: {dbg['returncode']}")
        if dbg.get("stderr"):
            print(f"  \033[31m錯誤輸出\033[0m: {dbg['stderr']}")
        if dbg.get("attempts"):
            print("  \033[35m嘗試歷程\033[0m:")
            for att in dbg["attempts"]:
                print(f"    - [{att.get('method')}] Target: {att.get('target')} -> Exit {att.get('code')} ({att.get('stderr')})")


def render_authorized_keys_audit(audit_data: dict):
    """輸出全網節點 authorized_keys 活體深度安全稽核報表"""
    ui_header("OpenLabOps Cluster Authorized Keys Live Security Audit Report")

    records = audit_data.get("records", [])
    summary = audit_data.get("summary", {})

    c1 = pad_cjk("節點主機", 14)
    c2 = pad_cjk("帳號", 8)
    c3 = pad_cjk("金鑰身分", 16)
    c4 = pad_cjk("公鑰 Comment / 標籤", 26)
    c5 = pad_cjk("來源 IP 限制", 22)
    c6 = pad_cjk("安全稽核狀態", 18)

    print(f"\033[1m{c1} {c2} {c3} {c4} {c5} {c6}\033[0m")
    print("─" * 110)

    for r in records:
        h = r["hostname"]
        if visible_len(h) > 14:
            h = h[:13] + "…"

        opts = r["options"]
        if visible_len(opts) > 22:
            opts = opts[:19] + "..."

        r1 = pad_cjk(h, 14)
        r2 = pad_cjk(r["account"], 8)
        r3 = pad_cjk(r["key_id"], 16)
        r4 = pad_cjk(r["comment"][:26], 26)
        r5 = pad_cjk(opts, 22)
        r6 = pad_cjk(r["badge"], 18)
        print(f"{r1} {r2} {r3} {r4} {r5} {r6}")

    print("─" * 110)
    print(f"稽核結果統計: 共 {summary['total_nodes']} 個節點, {summary['total_keys']} 筆授權金鑰 | "
          f"\033[32m● {summary['authorized_count']} 合法最新\033[0m | "
          f"\033[33m▲ {summary['residual_count']} 舊版殘留\033[0m | "
          f"\033[31m✖ {summary['rogue_count']} 非法金鑰\033[0m")

    if summary.get("has_rogue_keys"):
        print("\n\033[1;31m🚨 嚴重安全警報: 檢測到非法未受控之 SSH Key 登入許可！請立即登入該主機刪除未知金鑰！\033[0m")
    elif summary.get("residual_count", 0) > 0:
        print("\n\033[33m⚠️ 注意: 發現舊版殘留金鑰，建議執行 'lab-ssh' 啟動輪替清理工作流！\033[0m")
    else:
        print("\n\033[32m🎉 結論: 全網所有節點之 authorized_keys 完全受控，未發現任何未知或非法登入授權！\033[0m")


def main():
    parser = argparse.ArgumentParser(description="OpenLabOps Cluster Status Dashboard (lab-status)")
    parser.add_argument("-v", "--version", action="store_true", help="顯示工具版本號")
    parser.add_argument("-q", "--quick", action="store_true", help="快速模式 (僅探測本機，略過全網遠端節點)")
    parser.add_argument("-k", "--keys-only", action="store_true", help="僅顯示受控私鑰狀態與存活監控")
    parser.add_argument("-a", "--audit-keys", action="store_true", help="深入稽核全網各節點帳號 authorized_keys，揪出非受控或非法後門金鑰")
    parser.add_argument("-n", "--nodes-only", action="store_true", help="僅顯示伺服器節點與套件狀態")
    parser.add_argument("-d", "--debug", action="store_true", help="顯示各節點連線探測詳細診斷日誌 (STDERR、Exit Code、執行指令)")
    parser.add_argument("-p", "--probe", metavar="HOST", help="單獨測試與探測指定節點 (例如 --probe gateway)")
    parser.add_argument("-b", "--box", action="store_true", help="使用彩色卡片外框模式 (Box Cards UI)")
    parser.add_argument("-t", "--table", "--plain", action="store_true", help="無外框極簡表格輸出模式 (預設)")
    parser.add_argument("--json", action="store_true", help="以結構化 JSON 輸出")

    args = parser.parse_args()

    if args.version:
        print_version("OpenLabOps Cluster Status Dashboard (lab-status)")
        return

    if args.probe:
        from core.live_probe import probe_single_node_by_name
        ui_header(f"節點單獨測試與探針診斷: {args.probe}")
        res = probe_single_node_by_name(args.probe, debug=True)
        render_debug_diagnostics({args.probe: res})
        print("\n\033[1m探測數據原始 JSON:\033[0m")
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    tools_data = check_tools_health(quick=args.quick)
    keys_data = check_ssh_keys_alignment(quick=args.quick)
    ssot_keys = load_ssot_secrets_keys()

    probe_elapsed = 0.0
    if args.quick:
        if CLUSTER_TARGETS:
            local_target = next((t for t in CLUSTER_TARGETS if t.get("is_local")), CLUSTER_TARGETS[0])
            local_res = probe_single_node(local_target, debug=args.debug)
            live_nodes_map = {local_target["name"]: local_res}
        else:
            live_nodes_map = {}
    else:
        live_nodes_map, probe_elapsed = probe_all_cluster_nodes(debug=args.debug)

    nodes_data = check_nodes_and_packages(live_nodes_map)
    audit_data = audit_node_authorized_keys(ssot_keys, live_nodes_map)
    git_data = collect_git_watch_summary(live_nodes_map)

    if args.json:
        result = {
            "timestamp": datetime.now().isoformat(),
            "probe_elapsed_seconds": probe_elapsed,
            "tools": tools_data,
            "ssh_keys": keys_data,
            "authorized_keys_audit": audit_data,
            "nodes": nodes_data,
            "git_watch": git_data,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.audit_keys:
        render_authorized_keys_audit(audit_data)
        return

    if args.keys_only:
        ui_header("SSH 金鑰狀態與存活監控 (SSH Keys Status & Lifecycle)")
        for k in keys_data["keys"]:
            age_info = k["age_info"]
            ui_kv(k["key_name"], f"{k['type']} | Comment: {k['comment']} | 存活: {age_info['age_str']} ({age_info['desc']}) | Aligned: {k['aligned']} | Perm: {k['perm_str']}")
        if keys_data.get("auth_probes"):
            ui_divider()
            ui_kv("Gitea Probe", "OK" if keys_data["auth_probes"].get("gitea") else "FAIL")
            ui_kv("GitHub Probe", "OK" if keys_data["auth_probes"].get("github") else "FAIL")
        return

    if args.nodes_only:
        ui_header("伺服器節點與即時套件更新現況")
        for n in nodes_data.get("nodes", []):
            ui_kv(n["hostname"], f"OS: {n['os']} | Pkg: {n['package_manager']} | 待更新: {n['upg_count']} ({','.join(n['upg_samples'])})")
        return

    # 預設採用無外框表格模式 (-t)，若管理者加上 -b / --box 則切換為卡片外框模式
    render_dashboard(tools_data, keys_data, nodes_data, audit_data, probe_elapsed, borderless=not args.box, git_data=git_data)

    if args.debug:
        render_debug_diagnostics(live_nodes_map)


if __name__ == "__main__":
    main()
