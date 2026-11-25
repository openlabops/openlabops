# -*- coding: utf-8 -*-
"""
OpenLabOps Node Readiness & Lockout Guard
Implements [INV-02] and Boot Sync Lockout Contract:
- Non-7/24 nodes (desktops, laptops, intermittent nodes) MUST synchronize
  public keys on boot via systemd service from Gitea SSOT.
- Before lab-boot-sync completes and creates /run/openlab/synced_ok,
  the node is strictly locked out of all Ansible / lab-tools automation operations.
- Dev nodes (control-node, remote-dev) are master consoles with always_online: true.
"""

import os
import sys
import socket
import json
from pathlib import Path
from .config import get_cluster_prefix, get_manifest_path


def get_cluster_state_prefix() -> str:
    try:
        return get_cluster_prefix() or "openlab"
    except Exception:
        return "openlab"


SYNC_STAMP_FILE = Path(f"/run/{get_cluster_state_prefix()}/synced_ok")


def get_sync_stamp_file() -> Path:
    global SYNC_STAMP_FILE
    if SYNC_STAMP_FILE and str(SYNC_STAMP_FILE) != "/run/openlab/synced_ok" and str(SYNC_STAMP_FILE) != f"/run/{get_cluster_state_prefix()}/synced_ok":
        return SYNC_STAMP_FILE
    return Path(f"/run/{get_cluster_state_prefix()}/synced_ok")


def get_lockout_override_flag() -> str:
    return f"{get_cluster_state_prefix().upper()}_BYPASS_LOCKOUT"


def get_current_hostname() -> str:
    return socket.gethostname().split(".")[0].lower()


def is_node_intermittent() -> bool:
    """
    檢查當前節點是否為非 7/24 在線之客戶端工作站 (desktop / endpoint)。
    由 /etc/<prefix>/node.json、conf/nodes/<hostname>.json 或 current.json 判斷。
    """
    prefix = get_cluster_state_prefix()
    hname = get_current_hostname()
    candidate_paths = [
        Path(f"/etc/{prefix}/node.json"),
        Path(f"/usr/local/etc/{prefix}/nodes/{hname}.json"),
        Path(f"/usr/local/bin/{prefix}/conf/current.json"),
        Path(__file__).resolve().parent.parent.parent.parent / "conf" / "nodes" / f"{hname}.json",
    ]
    for p in candidate_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for n in data:
                        if (n.get("hostname") or "").lower() == hname.lower():
                            data = n
                            break
                if isinstance(data, dict):
                    if data.get("node_category") in ("desktop", "endpoint"):
                        return True
                    if data.get("always_online") is False:
                        return True
                    if data.get("node_category") in ("dev", "server", "appliance"):
                        return False
            except Exception:
                pass

    # 由共用 YAML 解析器動態檢查是否屬於 desktops 群組 (零寫死主機名與縮排 [INV-03])
    manifest_path = get_manifest_path()
    if manifest_path and manifest_path.exists():
        try:
            from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata
            meta_map = extract_manifest_hosts_metadata(parse_yaml_file(manifest_path))
            if hname in meta_map and meta_map[hname].get("category") == "desktop":
                return True
        except Exception:
            pass
    return False


def check_lockout_status() -> tuple:
    """
    回傳 (is_locked: bool, reason: str)
    若鎖定，回傳 True 與詳細說明；若正常，回傳 False 與空字串。
    """
    prefix = get_cluster_state_prefix()
    flag = get_lockout_override_flag()
    if os.environ.get(flag) == "1" or os.environ.get("OPENOPENLAB_BYPASS_LOCKOUT") == "1":
        return False, "Bypassed via environment flag."

    if not is_node_intermittent():
        return False, ""

    prefix = get_cluster_state_prefix()
    sync_stamp = get_sync_stamp_file()
    if not sync_stamp.exists():
        cmd_name = "lab-boot-sync"
        return True, (
            f"本機屬非 7/24 在線節點 (desktop / intermittent)，開機金鑰同步尚未完成。\n"
            f"未更新 Gitea SSOT 最新公鑰前，門禁機制阻斷所有 Ansible 與叢集維運功能！\n"
            f"請執行 'sudo {cmd_name}' 或等待 systemd 服務 ({cmd_name}.service) 完成同步。"
        )
    return False, ""

def enforce_lockout_guard(tool_name: str = "", allow_readonly: bool = False):
    """
    呼叫此函數可在執行任何維運/Ansible 操作前進行門禁檢查。
    若被鎖定且非唯讀操作，直接印出警告並 exit(1)。
    """
    if allow_readonly:
        return True
    is_locked, reason = check_lockout_status()
    if is_locked:
        prefix = f" ({tool_name})" if tool_name else ""
        sys.stderr.write(f"\n\033[1;31m[!] 門禁阻斷 (NODE LOCKOUT){prefix} [INV-02]:\033[0m\n{reason}\n\n")
        sys.exit(1)
    return True


check_boot_sync_lockout = enforce_lockout_guard

