#!/usr/bin/env python3
"""
OpenLabOps Endpoint Toolchain: Host SSH Key Revocation Tool
適用於 Homelab 高權限區域或任一具備 Gitea Token 之主機：
1. 接收指定的端點名稱 ($hostname，例如 laptop, desktop, workstation)
2. 透過 Gitea Action Dispatch API 呼叫 revoke-host-key.yml
3. 同步自全網受控伺服器群 (servers) 的 labadmin 帳號 authorized_keys 中剔除該端點公鑰
4. 可選：自 openlab-secrets 倉庫刪除 $hostname.pub，完成定點抹除 (Wipe)
"""

import os
import sys
import argparse
import subprocess

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_confirm, ui_checklist
from core.gitea_api import gitea_dispatch

from pathlib import Path

def _detect_repo_dir(rel_names: list, fallback: Path) -> str:
    for base in [Path(__file__).resolve().parent.parent.parent, Path.home()]:
        for rel in rel_names:
            p = base / rel
            if p.exists():
                return str(p)
    return str(fallback)

ANSIBLE_DIR = _detect_repo_dir(["ansible", "openlab-ansible", "openlabops/ansible"], Path.home() / "openlab-ansible")
SECRETS_DIR = _detect_repo_dir(["secrets", "openlab-secrets", "openlab-secrets"], Path.home() / "openlab-secrets")
PLAYBOOK_PATH = os.path.join(ANSIBLE_DIR, "playbooks/revoke-host-key.yml")
INVENTORY_PATH = os.path.join(ANSIBLE_DIR, "inventory/hosts.yml")


def revoke_key_via_api(hostname: str, purge_secrets: bool = True) -> bool:
    """呼叫 Gitea Actions API 執行遠端定點清除"""
    ui_info(f"正在透過 Gitea Action API 派發清除端點 [{hostname}] 公鑰...")
    payload = {
        "ref": "main",
        "inputs": {
            "host_name": hostname,
            "purge_secrets": "true" if purge_secrets else "false",
        }
    }
    return gitea_dispatch("revoke-host-key.yml", payload)


def revoke_key_via_local(hostname: str, purge_secrets: bool = True) -> bool:
    """在 Homelab 管理機直接透過本地 Ansible 執行清除"""
    if not os.path.exists(PLAYBOOK_PATH) or not os.path.exists(INVENTORY_PATH):
        ui_warn("找不到本地 Ansible 劇本或 Inventory，改用 Gitea API 派發。")
        return revoke_key_via_api(hostname, purge_secrets)

    cmd = [
        "ansible-playbook",
        "-i", INVENTORY_PATH,
        PLAYBOOK_PATH,
        "--extra-vars", f"host_name={hostname}"
    ]
    ui_info(f"執行本地 Ansible 指令: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        ui_error(f"本地 Ansible 清除失敗，回傳碼: {res.returncode}")
        return False

    ui_success(f"[{hostname}] 公鑰已成功從全網伺服器 authorized_keys 清除！")

    if purge_secrets:
        pub_file = os.path.join(SECRETS_DIR, "ssh-key", f"{hostname}.pub")
        if os.path.exists(pub_file):
            ui_info(f"正在自本地 openlab-secrets 移除 {hostname}.pub...")
            try:
                subprocess.run(["git", "-C", SECRETS_DIR, "rm", "-f", f"ssh-key/{hostname}.pub"], check=True)
                subprocess.run(["git", "-C", SECRETS_DIR, "commit", "-m", f"feat(ssh): revoke and remove {hostname}.pub [skip ci]"], check=True)
                subprocess.run(["git", "-C", SECRETS_DIR, "push", "origin", "main"], check=True)
                ui_success(f"openlab-secrets 中的 [{hostname}.pub] 已同步刪除並推播。")
            except Exception as e:
                ui_warn(f"清理 openlab-secrets 倉庫時發生異常: {e}")

    return True


def get_available_endpoint_keys() -> list:
    """掃描已註冊之端點公鑰清單"""
    keys = []
    secrets_pub_dir = os.path.join(SECRETS_DIR, "ssh-key")
    if os.path.exists(secrets_pub_dir):
        for f in os.listdir(secrets_pub_dir):
            if f.endswith(".pub"):
                name = f[:-4]
                if name not in ("lab", "ansible", "storage", "gateway", "id_ed25519", "id_rsa"):
                    keys.append(name)
    ssh_dir = os.path.expanduser("~/.ssh")
    if os.path.exists(ssh_dir):
        for f in os.listdir(ssh_dir):
            if f.endswith(".pub") and not f.endswith(".key.pub"):
                name = f[:-4]
                if name not in ("lab", "ansible", "storage", "gateway", "id_ed25519", "id_rsa") and name not in keys:
                    keys.append(name)
    return sorted(keys)


def revoke_endpoint_key(hostname: str, purge_secrets: bool = True, force_local: bool = False) -> bool:
    """整合清除流程入口"""
    if force_local:
        return revoke_key_via_local(hostname, purge_secrets)
    else:
        return revoke_key_via_api(hostname, purge_secrets)


def main(args_list=None):
    if len(sys.argv) > 1 and sys.argv[1] in ("-v", "--version", "version"):
        from core.version import print_version
        print_version("OpenLabOps Endpoint SSH Key Revocation Tool")
        return

    from core.i18n import t
    parser = argparse.ArgumentParser(prog="revoke-host-ssh-key", description=t("revoke_key.cli_desc", "OpenLabOps Endpoint SSH Key Revocation Tool"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-H", "--hostname", type=str, required=False, default=None, help=t("revoke_key.cli_hostname", "Endpoint hostname whose public key should be revoked"))
    parser.add_argument("--keep-secrets", action="store_true", help=t("revoke_key.cli_keep", "Keep public key backup in openlab-secrets repo"))
    parser.add_argument("-l", "--local", action="store_true", help=t("revoke_key.cli_local", "Force local Ansible execution (default: Gitea API)"))
    parser.add_argument("-y", "--yes", "-f", "--force", dest="auto_confirm", action="store_true", help=t("revoke_key.cli_yes", "Skip confirmation prompt"))

    args = parser.parse_args(args_list) if args_list is not None else parser.parse_args()
    purge_secrets = not args.keep_secrets

    target_hosts = []
    if args.hostname:
        target_hosts = [args.hostname.strip().lower()]
    else:
        candidates = get_available_endpoint_keys()
        if not candidates:
            ui_warn("未在 openlab-secrets 或 ~/.ssh 偵測到任何獨立端點公鑰。")
            manual = input("請直接手動輸入欲清除公鑰之端點主機名稱: ").strip().lower()
            if manual:
                target_hosts = [manual]
            else:
                return
        else:
            options = [f"{c}.pub (端點: {c})" for c in candidates]
            ui_header("🚫 獨立端點 SSH 公鑰定點清除 (Checklist 模式)")
            selected_indices = ui_checklist("請勾選欲自全網伺服器徹底清除之端點公鑰 (空白鍵切換 [X]):", options)
            if not selected_indices:
                ui_warn("未選取任何端點公鑰，操作取消。")
                return
            target_hosts = [candidates[i - 1] for i in selected_indices]

    ui_header(f"🚫 獨立端點 SSH 公鑰定點清除 - 共選取 {len(target_hosts)} 個端點")
    ui_kv("目標端點清單", ", ".join(target_hosts))
    ui_kv("受影響主機群", "servers:!hypervisors:!storage (所有在線受控伺服器)")
    ui_kv("清理帳號", "labadmin")
    ui_kv("同步清除倉庫公鑰", "是 (Purge from openlab-secrets)" if purge_secrets else "否 (保留備份)")
    ui_kv("執行模式", "本地 Ansible 執行" if args.local else "Gitea Actions API 遠端派發")
    ui_divider()

    if not args.auto_confirm and not ui_confirm(f"⚠️ 確定要從全網伺服器徹底清除上述 {len(target_hosts)} 個端點的 SSH 公鑰？", "n"):
        ui_warn("操作已取消。")
        return

    all_success = True
    for hostname in target_hosts:
        ui_info(f"正在執行端點 [{hostname}] 公鑰清除任務...")
        success = revoke_endpoint_key(hostname, purge_secrets=purge_secrets, force_local=args.local)
        if success:
            ui_success(f"✨ 端點 [{hostname}] 公鑰已成功定點抹除！")
        else:
            ui_error(f"❌ 端點 [{hostname}] 公鑰清除任務失敗，請檢查日誌。")
            all_success = False

    if not all_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
