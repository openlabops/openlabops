#!/usr/bin/env python3
"""
OpenLabOps Tool: SSH Master & Host Key Sync Tool (~/.ssh/*.key)
負責從 Gitea REST API (openlab-secrets) 或本機機密庫獲取受控 SSH 金鑰對並更新本機配置。
支援管理金鑰 (openlab, lab, git-openlab) 與端點公鑰同步。
"""

import os
import sys
import shutil
import argparse
import urllib.request
import urllib.error

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.gitea_api import load_gitea_token, GITEA_URL, REPO_OWNER
from core.config import get_path, get_managed_keys, get_repo_name, TOOLS_ROOT

SSH_DIR = get_path("ssh_dir", os.path.expanduser("~/.ssh"))
dev_secrets = TOOLS_ROOT.parent / "openlab-secrets" / "ssh-key"
LOCAL_SECRETS_DIR = str(dev_secrets) if dev_secrets.exists() else ""

_keys = get_managed_keys()
DEFAULT_MANAGED_KEYS = []
for _k in _keys:
    _name = _k["name"] if isinstance(_k, dict) else _k
    DEFAULT_MANAGED_KEYS.append(_name)
    _base = _name.rsplit(".", 1)[0]
    DEFAULT_MANAGED_KEYS.append(f"{_base}.pub")
DEFAULT_MANAGED_KEYS = list(dict.fromkeys(DEFAULT_MANAGED_KEYS))


def fetch_remote_key_content(key_name: str) -> str:
    """從 Gitea REST API 或本機 secrets 倉庫獲取指定金鑰內容"""
    token = load_gitea_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    sec_repo = get_repo_name("secrets")
    api_url = f"{GITEA_URL}/api/v1/repos/{REPO_OWNER}/{sec_repo}/raw/ssh-key/{key_name}"

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                content = resp.read().decode("utf-8")
                if content:
                    return content
    except Exception:
        pass

    # Fallback to local secrets repo if available
    local_path = os.path.join(LOCAL_SECRETS_DIR, key_name)
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass

    return ""


def sync_ssh_keys(keys=None, check_only: bool = False, force: bool = False) -> bool:
    """同步並部署受控 SSH 金鑰至 ~/.ssh/"""
    if keys is None:
        keys = DEFAULT_MANAGED_KEYS

    os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(SSH_DIR, 0o700)
    except Exception:
        pass

    all_ok = True
    updated_count = 0

    for key_name in keys:
        target_path = os.path.join(SSH_DIR, key_name)
        remote_content = fetch_remote_key_content(key_name)

        if not remote_content:
            ui_warn(f"[{key_name}] 無法從 Gitea API 或機密庫獲取，略過。")
            all_ok = False
            continue

        existing_content = ""
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    existing_content = f.read()
            except Exception:
                pass

        is_priv = key_name.endswith(".key")
        expected_perm = 0o600 if is_priv else 0o644

        if existing_content.strip() == remote_content.strip():
            # Check permissions
            current_perm = oct(os.stat(target_path).st_mode & 0o777)
            if (os.stat(target_path).st_mode & 0o777) != expected_perm:
                os.chmod(target_path, expected_perm)
                ui_info(f"[{key_name}] 內容一致，更新權限為 {oct(expected_perm)}。")
            else:
                ui_info(f"[{key_name}] 已是最新且權限正常。")
            continue

        if check_only:
            ui_warn(f"[{key_name}] 偵測到本機與遠端機密庫存在差異！(check-only 模式未寫入)")
            continue

        # Write new content
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(remote_content)
        os.chmod(target_path, expected_perm)
        ui_success(f"[{key_name}] ✨ 成功同步並部署至 {target_path} (權限: {oct(expected_perm)})")
        updated_count += 1

    return all_ok


def main():
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="sync-ssh-keys", description=t("sync_keys.cli_desc", "OpenLabOps Managed SSH Key Sync Tool"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-n", "--node", type=str, help=t("sync_keys.cli_node", "Target node/group to deploy keys via Gitea Runner (e.g. control-node, servers)"))
    parser.add_argument("-u", "--user", type=str, default="labadmin", help=t("sync_keys.cli_user", "Target user on remote node (default: labadmin)"))
    parser.add_argument("-k", "--keys", nargs="+", default=DEFAULT_MANAGED_KEYS,
                        help=t("sync_keys.cli_keys", "List of managed key names to sync"))
    parser.add_argument("-c", "--check", action="store_true", help=t("sync_keys.cli_check", "Check for differences without writing changes"))
    parser.add_argument("-f", "--force", action="store_true", help=t("sync_keys.cli_force", "Force overwrite and fix permissions"))

    args = parser.parse_args()

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Managed SSH Key Sync Tool")
        return

    if args.node:
        ui_header("OpenLabOps SSH 金鑰遠端節點部署 (Runner Playbook)")
        ui_kv("目標節點", args.node)
        ui_kv("目標使用者", args.user)
        ui_kv("執行模式", "Gitea Actions CI/CD Runner (deploy-ssh-keys.yml)")
        ui_divider()
        payload = {
            "ref": "main",
            "inputs": {
                "target_hosts": args.node,
                "target_user": args.user,
                "deploy_client_keys": "true",
                "deploy_authorized_keys": "true",
                "deploy_ssh_config": "true"
            }
        }
        from core.gitea_api import gitea_dispatch
        success = gitea_dispatch("deploy-ssh-keys.yml", payload)
        if success:
            ui_success(f"已成功向 Gitea Actions 派發部署任務！請稍候查看執行紀錄。")
        return

    ui_header("OpenLabOps Managed SSH Key 同步工具")
    ui_kv("目標存放目錄", SSH_DIR)
    ui_kv("同步金鑰清冊", ", ".join(args.keys))
    ui_divider()

    sync_ssh_keys(keys=args.keys, check_only=args.check, force=args.force)


if __name__ == "__main__":
    main()
