#!/usr/bin/env python3
"""
OpenLabOps Endpoint Toolchain: Host SSH Key Generator & Deployment Tool
適用於不在 inventory 被控群組內的獨立端點 ($hostname: 如 laptop, desktop, workstation)
1. 於本地生成「帶有密碼 (Passphrase)」的 Ed25519 金鑰對 (~/.ssh/$hostname.key / ~/.ssh/$hostname.pub)
2. 支援「零 Clone (Zero-Clone)」邊緣節點模式：
   - 開發環境 (存在 openlab-secrets 倉庫)：本地同步並 commit & push
   - 邊緣節點 (無 homelab 倉庫 / 無本地 Ansible)：直接由 Gitea CI 接收公鑰字串並寫入遠端倉庫
3. 透過 Gitea CI Runner 或本地 Ansible 將公鑰套用至伺服器群 (servers) 的 labadmin 帳號 authorized_keys
"""

import os
import sys
import shutil
import argparse
import subprocess
import socket
import time
import getpass
import platform
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_confirm
from core.gitea_api import gitea_dispatch

# 基礎預設路徑
SSH_DIR = os.path.expanduser("~/.ssh")

def _detect_repo_dir(rel_names: list, fallback: Path) -> str:
    for base in [Path(__file__).resolve().parent.parent.parent, Path.home()]:
        for rel in rel_names:
            p = base / rel
            if p.exists():
                return str(p)
    return str(fallback)

ANSIBLE_DIR = _detect_repo_dir(["ansible", "openlab-ansible", "openlabops/ansible"], Path.home() / "openlab-ansible")
_secrets_base = _detect_repo_dir(["secrets", "openlab-secrets", "openlab-secrets"], Path.home() / "openlab-secrets")
SECRETS_KEY_DIR = os.path.join(_secrets_base, "ssh-key")
PLAYBOOK_PATH = os.path.join(ANSIBLE_DIR, "playbooks/deploy-host-key.yml")
INVENTORY_PATH = os.path.join(ANSIBLE_DIR, "inventory/hosts.yml")


def is_wsl() -> bool:
    """檢測當前執行環境是否為 WSL (Windows Subsystem for Linux)"""
    try:
        if "microsoft" in platform.release().lower() or "wsl" in platform.release().lower():
            return True
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r", encoding="utf-8") as f:
                content = f.read().lower()
                if "microsoft" in content or "wsl" in content:
                    return True
    except Exception:
        pass
    return False


def get_default_endpoint_name() -> str:
    """自動偵測端點名稱；若為 WSL 內核且主機名未標記 wsl，自動加上 _wsl 後綴"""
    base = socket.gethostname().split('.')[0].lower()
    if is_wsl() and "wsl" not in base:
        return f"{base}_wsl"
    return base



def generate_host_ssh_key(hostname: str, force_recreate: bool = False, passphrase: str = None) -> tuple:
    """為獨立端點 [$hostname] 生成帶密碼的 Ed25519 SSH 金鑰對 (儲存於 ~/.ssh/)"""
    os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(SSH_DIR, 0o700)
    except Exception:
        pass

    key_path = os.path.join(SSH_DIR, f"{hostname}.key")
    pub_path = os.path.join(SSH_DIR, f"{hostname}.pub")

    if os.path.exists(key_path) and not force_recreate:
        ui_info(f"偵測到現有私鑰: {key_path}，將使用此金鑰進行同步與部署。")
        return key_path, pub_path

    if os.path.exists(key_path) and force_recreate:
        ui_warn(f"正在覆蓋舊有私鑰: {key_path}")
        os.remove(key_path)
        if os.path.exists(pub_path):
            os.remove(pub_path)

    # 提示使用者輸入金鑰保護密碼 (Passphrase)
    if passphrase is None:
        print(f"\n🔐 請輸入保護 [{hostname}.key] 私鑰的密碼 (Passphrase):")
        passphrase = getpass.getpass("密碼 (按 Enter 可設定空密碼): ")
        if passphrase:
            confirm_pass = getpass.getpass("再次確認密碼: ")
            if passphrase != confirm_pass:
                ui_error("密碼輸入不一致，終止生成流程。")
                return "", ""

    comment = f"homelab-{hostname}-{time.strftime('%Y%m%d')}"
    cmd = [
        "ssh-keygen", "-t", "ed25519", "-N", passphrase or "",
        "-C", comment, "-f", key_path
    ]

    ui_info(f"正在為獨立端點 [{hostname}] 生成帶密碼保護的 Ed25519 金鑰對...")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        os.chmod(key_path, 0o600)
        # ssh-keygen 產出為 key_path + ".pub" (如 hostname.key.pub)，標準化為 hostname.pub
        default_gen_pub = key_path + ".pub"
        if os.path.exists(default_gen_pub) and default_gen_pub != pub_path:
            shutil.move(default_gen_pub, pub_path)
        if os.path.exists(pub_path):
            os.chmod(pub_path, 0o644)
        ui_success(f"成功生成端點 [{hostname}] 金鑰對！(Comment: {comment})")
        return key_path, pub_path
    except subprocess.CalledProcessError as e:
        ui_error(f"生成 SSH Key 失敗: {e.stderr}")
        return "", ""


def sync_pub_to_secrets(hostname: str, local_pub_path: str) -> str:
    """
    若本機為開發環境且存在 openlab-secrets 倉庫，同步公鑰至倉庫並 commit & push；
    若為邊緣節點 (無本地 repo)，則提示由遠端 CI Runner 處理。
    """
    if not os.path.exists(local_pub_path):
        ui_error(f"找不到本地公鑰檔案: {local_pub_path}")
        return ""

    secrets_repo_dir = os.path.dirname(SECRETS_KEY_DIR)
    secrets_git_dir = os.path.join(secrets_repo_dir, ".git")

    # 邊緣端點無本地 Git 倉庫
    if not os.path.exists(secrets_git_dir):
        ui_info("端點處於零 Clone 模式 (非開發環境，無本機 openlab-secrets 倉庫)。")
        ui_info("將於下一步透過 Gitea CI 自動將公鑰寫入遠端倉庫並執行全網部署。")
        return local_pub_path

    # 開發機本地倉庫同步
    os.makedirs(SECRETS_KEY_DIR, exist_ok=True)
    secrets_pub_path = os.path.join(SECRETS_KEY_DIR, f"{hostname}.pub")
    try:
        with open(local_pub_path, "r", encoding="utf-8") as src, open(secrets_pub_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())

        ui_success(f"端點公鑰已同步至本機 openlab-secrets: {secrets_pub_path}")
        rel_pub = os.path.join("ssh-key", f"{hostname}.pub")
        subprocess.run(["git", "add", rel_pub], cwd=secrets_repo_dir, capture_output=True)
        commit_res = subprocess.run(
            ["git", "commit", "-m", f"feat(ssh): add/update endpoint {hostname}.pub key"],
            cwd=secrets_repo_dir, capture_output=True, text=True
        )
        if commit_res.returncode == 0:
            ui_success(f"已將 {hostname}.pub 提交至本機 openlab-secrets Git 倉庫。")
            push_res = subprocess.run(["git", "push"], cwd=secrets_repo_dir, capture_output=True, text=True)
            if push_res.returncode == 0:
                ui_success("已推送到 openlab-secrets 遠端倉庫。")

        return secrets_pub_path
    except Exception as e:
        ui_warn(f"本機 openlab-secrets 同步略過或發生警告: {e}")
        return local_pub_path


def apply_key_to_servers(hostname: str, pub_path: str, use_gitea: bool = False) -> bool:
    """透過 Gitea Actions 或本地 Ansible 將 $hostname.pub apply 到伺服器群 (servers) 的 labadmin 帳號 authorized_keys"""
    if not os.path.exists(pub_path):
        ui_error(f"找不到本地公鑰檔案: {pub_path}")
        return False

    with open(pub_path, "r", encoding="utf-8") as f:
        pub_content = f.read().strip()

    # 檢查本地是否具備執行 Ansible Playbook 之環境
    has_ansible = (
        shutil.which("ansible-playbook") is not None
        and os.path.exists(PLAYBOOK_PATH)
        and os.path.exists(INVENTORY_PATH)
    )

    if use_gitea or not has_ansible:
        if not has_ansible and not use_gitea:
            ui_info("偵測到本機無 Ansible 環境或缺少本地劇本，自動切換為 Gitea CI Runner 派發...")
        ui_info("發送 Gitea Action Dispatch 請求 (傳遞端點公鑰內容)...")
        payload = {
            "ref": "main",
            "inputs": {
                "host_name": hostname,
                "pub_key": pub_content
            }
        }
        return gitea_dispatch("deploy-host-key.yml", payload)
    else:
        cmd = [
            "ansible-playbook",
            "-i", INVENTORY_PATH,
            PLAYBOOK_PATH,
            "--extra-vars", f"host_name={hostname}",
            "--extra-vars", f"host_pub_key_path={pub_path}"
        ]
        ui_info(f"執行本地 Ansible 指令: {' '.join(cmd)}")
        res = subprocess.run(cmd)
        if res.returncode == 0:
            ui_success(f"[{hostname}.pub] 已成功 apply 至全網伺服器群 (servers) labadmin 帳號！")
            return True
        else:
            ui_warn(f"Ansible Playbook 執行回傳碼: {res.returncode}")
            return False


def main():
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="generate-host-ssh-key", description=t("gen_key.cli_desc", "OpenLabOps Endpoint SSH Key Toolchain"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-H", "--hostname", type=str, help=t("gen_key.cli_hostname", "Endpoint hostname (e.g. laptop, desktop, workstation)"))
    parser.add_argument("-f", "--force", action="store_true", help=t("gen_key.cli_force", "Force regenerate SSH keypair"))
    parser.add_argument("-P", "--passphrase", type=str, help=t("gen_key.cli_passphrase", "Specify private key passphrase (default: interactive prompt)"))
    parser.add_argument("-g", "--gitea", action="store_true", help=t("gen_key.cli_gitea", "Force dispatch deployment via Gitea CI Runner"))

    args = parser.parse_args()

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Endpoint SSH Key Toolchain")
        return

    hostname = args.hostname or get_default_endpoint_name()
    if not args.hostname and is_wsl():
        ui_info(f"💡 偵測到 WSL 執行環境，端點名稱自動辨識為: {hostname}")

    ui_header(f"獨立端點 [$hostname] SSH Key 工具鏈 - 端點名稱: {hostname}")
    ui_kv("端點類型", "非 Inventory 被控伺服器 (Client Endpoint)" + (" [WSL 環境]" if is_wsl() else ""))
    ui_kv("私鑰位置 (Passphrase 密碼保護)", os.path.join(SSH_DIR, f"{hostname}.key"))
    ui_kv("公鑰位置", os.path.join(SSH_DIR, f"{hostname}.pub"))
    ui_kv("Ansible Apply 目標群組", "servers (24/7 伺服器群)")
    ui_kv("Ansible Apply 目標帳號", "labadmin")
    ui_divider()

    # 1. 本地生成帶密碼保護的 SSH Key Pair (優先於 ~/.ssh/)
    key_path, pub_path = generate_host_ssh_key(hostname, force_recreate=args.force, passphrase=args.passphrase)
    if not key_path or not pub_path:
        sys.exit(1)

    # 2. 同步公鑰 (開發環境寫入本地 secrets repo，邊緣節點保留本地 pub 由 CI 處理)
    sync_pub_path = sync_pub_to_secrets(hostname, pub_path)

    # 3. 透過 Gitea CI 或 Ansible 將公鑰 apply 至伺服器群 labadmin 帳號
    if ui_confirm(f"確定要將 [{hostname}.pub] 套用 (Apply) 至伺服器群 (servers) 的 labadmin 帳號？", "y"):
        apply_key_to_servers(hostname, sync_pub_path or pub_path, use_gitea=args.gitea)

    ui_divider()
    ui_success(f"✨ 獨立端點 [{hostname}] SSH Key 產生、同步與伺服器套用流程完畢！")


if __name__ == "__main__":
    main()

