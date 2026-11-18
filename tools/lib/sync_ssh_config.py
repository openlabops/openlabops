#!/usr/bin/env python3
"""
OpenLabOps Tool: SSH Client Config Sync Tool (~/.ssh/config)
負責從 Gitea REST API 或 Central Repo 抓取標準 ~/.ssh/config 並更新本機配置。
支援雙版本分流 (Profile)：
  - openlab: 內部成員/管理機版本 (含全網伺服器與 Appliance 底層設備，依賴 id_user.key / ansible.key)
  - endpoint : 外部端點版本 (工作站/筆電端點，純伺服器別名，僅依賴本機端點私鑰，排除 Appliance)
"""

import os
import sys
import time
import shutil
import socket
import argparse
import urllib.request
import urllib.error

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_confirm
from core.gitea_api import load_gitea_token, GITEA_URL, REPO_OWNER
from core.config import get_path, get_endpoint_hosts, get_repo_name, TOOLS_ROOT

SSH_DIR = get_path("ssh_dir", os.path.expanduser("~/.ssh"))
SSH_CONFIG_PATH = os.path.join(SSH_DIR, "config")

dev_configs = TOOLS_ROOT.parent / "openlab-configs"
dev_secrets = TOOLS_ROOT.parent / "openlab-secrets"

LOCAL_OPENLAB_CONFIGS = [
    str(dev_configs / "ssh-config" / "openlab" / "config"),
    str(dev_secrets / "ssh-config" / "config"),
    str(dev_configs / "ssh-config" / "client" / "config"),
] if dev_configs.exists() or dev_secrets.exists() else []

LOCAL_ENDPOINT_CONFIGS = [
    str(dev_configs / "ssh-config" / "endpoint" / "config"),
] if dev_configs.exists() else []


def detect_default_profile() -> str:
    """依據當前主機名稱自動判斷適用版本"""
    hostname = socket.gethostname().lower()
    endpoint_hosts = get_endpoint_hosts()
    for ep in endpoint_hosts:
        if ep in hostname:
            return "endpoint"
    return "openlab"


def fetch_remote_ssh_config(profile: str = "openlab") -> str:
    """從 Gitea REST API 獲取指定 Profile 的最新標準 ~/.ssh/config 內容"""
    token = load_gitea_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    cfg_repo = get_repo_name("configs")
    sec_repo = get_repo_name("secrets")

    if profile == "endpoint":
        candidates = [
            f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{cfg_repo}/raw/ssh-config/endpoint/config",
        ]
        local_fallbacks = LOCAL_ENDPOINT_CONFIGS
    else:
        candidates = [
            f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{cfg_repo}/raw/ssh-config/openlab/config",
            f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{cfg_repo}/raw/ssh-config/config",
            f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{sec_repo}/raw/ssh-config/config",
            f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{cfg_repo}/raw/ssh-config/client/config",
        ]
        local_fallbacks = LOCAL_OPENLAB_CONFIGS

    for url in candidates:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    content = resp.read().decode("utf-8")
                    if content and "Host" in content:
                        ui_info(f"成功從 Gitea API 取得 SSH Config ({profile}: {url.split('/')[-3]})")
                        return content
        except Exception:
            continue

    # 若 Gitea 連線失敗，檢查本機是否存在 repo 檔案 (開發環境 / 控制節點本地倉 fallback)
    dynamic_fallbacks = list(local_fallbacks)
    env_cfg = os.environ.get("WORKSPACE_CONFIGS_DIR", "").strip()
    search_roots = [p for p in [
        env_cfg,
        os.path.expanduser(f"~/{cfg_repo}"),
        str(TOOLS_ROOT.parent / cfg_repo),
        str(TOOLS_ROOT.parent.parent / cfg_repo),
    ] if p]
    subpaths = (
        [os.path.join("ssh-config", "endpoint", "config")]
        if profile == "endpoint"
        else [
            os.path.join("ssh-config", "openlab", "config"),
            os.path.join("ssh-config", "config"),
            os.path.join("ssh-config", "client", "config"),
        ]
    )
    for root in search_roots:
        for sub in subpaths:
            cand = os.path.join(root, sub)
            if cand not in dynamic_fallbacks:
                dynamic_fallbacks.append(cand)

    for local_path in dynamic_fallbacks:
        if os.path.exists(local_path):
            ui_info(f"使用本機現存倉庫組態 ({profile}): {local_path}")
            with open(local_path, "r", encoding="utf-8") as f:
                return f.read()

    return ""


def sync_ssh_config(target_path: str = SSH_CONFIG_PATH, profile: str = "openlab", force: bool = False, check_only: bool = False) -> bool:
    """同步並部署 ~/.ssh/config"""
    ssh_parent = os.path.dirname(target_path)
    os.makedirs(ssh_parent, mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(ssh_parent, "sockets"), mode=0o700, exist_ok=True)
    try:
        os.chmod(ssh_parent, 0o700)
        os.chmod(os.path.join(ssh_parent, "sockets"), 0o700)
    except Exception:
        pass

    remote_content = fetch_remote_ssh_config(profile=profile)
    if not remote_content:
        ui_error(f"無法從 Gitea API 或本機倉庫獲取 SSH Client Config (版本: {profile})！")
        return False

    existing_content = ""
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            existing_content = f.read()

    if existing_content.strip() == remote_content.strip():
        ui_success(f"目前本機 SSH Config ({target_path}) 與 {profile} 版本一致，已是最新狀態。")
        try:
            os.chmod(target_path, 0o600)
        except Exception:
            pass
        return True

    if check_only:
        ui_warn(f"偵測到本機 SSH Config 與遠端 {profile} 標準配置存在差異！(check-only 模式未寫入)")
        return False

    # 若已有舊檔案且非強制，建立備份
    if os.path.exists(target_path):
        backup_path = f"{target_path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(target_path, backup_path)
        ui_info(f"已建立現有設定檔備份: {backup_path}")

    # 寫入新設定並設為 0600
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(remote_content)
    try:
        os.chmod(target_path, 0o600)
    except Exception:
        pass

    ui_success(f"✨ 成功同步 [{profile}] 標準 SSH Config 至: {target_path} (權限: 0600)")
    return True


def main():
    from core.i18n import t
    detected_profile = detect_default_profile()
    parser = argparse.ArgumentParser(prog="sync-ssh-config", description=t("sync_cfg.cli_desc", "OpenLabOps Standard SSH Client Config Sync Tool"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-t", "--target", type=str, default=SSH_CONFIG_PATH, help=t("sync_cfg.cli_target", "Target SSH config path (default: ~/.ssh/config)"))
    parser.add_argument("-p", "--profile", type=str, choices=["openlab", "endpoint"], default=detected_profile,
                        help=t("sync_cfg.cli_profile", f"Select config profile (openlab or endpoint; detected: {detected_profile})", profile=detected_profile))
    parser.add_argument("-c", "--check", action="store_true", help=t("sync_cfg.cli_check", "Check for differences without writing changes"))
    parser.add_argument("-f", "--force", action="store_true", help=t("sync_cfg.cli_force", "Force overwrite and backup existing file"))

    args = parser.parse_args()

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Standard SSH Client Config Sync Tool")
        return

    ui_header("OpenLabOps Standard SSH Client Config 同步工具")
    ui_kv("目標設定路徑", args.target)
    ui_kv("套用版本 Profile", f"{args.profile} (系統自適配: {detected_profile})")
    if args.profile == "openlab":
        ui_kv("主連線金鑰", "~/.ssh/id_user.key (萬能), ~/.ssh/ansible.key (運維)")
    else:
        ui_kv("主連線金鑰", "~/.ssh/%h.key (本機端點專屬私鑰，無全網管理金鑰)")
    ui_divider()

    if not sync_ssh_config(target_path=args.target, profile=args.profile, force=args.force, check_only=args.check):
        sys.exit(1)


if __name__ == "__main__":
    main()
