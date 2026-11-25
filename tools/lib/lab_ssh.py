#!/usr/bin/env python3
"""
OpenLabOps Cluster SSH Key Management & Rotation Suite (lab-ssh)
負責統籌全網伺服器 SSH 金鑰輪換 (Lab, OpenLabOps/Virtualization, Git-OpenLabOps)、
端點金鑰生成 (WSL 自動辨識)、定點清除 (Revoke) 與客戶端金鑰同步。
"""

import os
import sys
import socket
import platform
import argparse

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_select, ui_confirm
from core.config import get_cluster_prefix, is_openlab
from core.version import get_local_version
from core.gitea_api import gitea_dispatch
from sync_ssh_config import sync_ssh_config
from sync_ssh_keys import sync_ssh_keys
from revoke_host_ssh_key import revoke_endpoint_key, main as revoke_main
from generate_host_ssh_key import generate_host_ssh_key, sync_pub_to_secrets, apply_key_to_servers, get_default_endpoint_name, is_wsl


def rotate_ansible_keys(target_nodes: str = "dev") -> bool:
    target_desc = f" (同步私鑰至工作端點: {target_nodes})" if target_nodes else ""
    ui_info(f"正在向 Gitea Actions 派發 Ansible 自動化金鑰輪換工作流{target_desc}...")
    return gitea_dispatch("rotate-ansible-keys.yml", {
        "ref": "main",
        "inputs": {"target_nodes": target_nodes}
    })

# 向後相容別名
rotate_ansible_keys = rotate_ansible_keys


def rotate_storage_keys(target_nodes: str = "dev") -> bool:
    if get_cluster_prefix() == "openlab":
        ui_info("OpenLabOps 環境不支援專用儲存設備金鑰輪換（特化設備已排除）。")
        return True
    target_desc = f" (同步私鑰至工作端點: {target_nodes})" if target_nodes else ""
    ui_info(f"正在向 Gitea Actions 派發 儲存與設備 (Storage & Appliances) 金鑰輪換工作流{target_desc}...")
    return gitea_dispatch("rotate-storage-keys.yml", {
        "ref": "main",
        "inputs": {"target_nodes": target_nodes}
    })

# 向後相容別名
rotate_openlab_keys = rotate_storage_keys


def rotate_git_keys(target_nodes: str = "all:!appliances") -> bool:
    target_desc = f" (同步私鑰至工作端點: {target_nodes})" if target_nodes else ""
    ui_info(f"正在向 Gitea Actions 派發 Git 平台認證金鑰輪換工作流{target_desc}...")
    return gitea_dispatch("rotate-git-keys.yml", {
        "ref": "main",
        "inputs": {"target_nodes": target_nodes}
    })


def rotate_all_server_keys(target_nodes: str = "dev") -> bool:
    """一鍵依序輪換所有伺服器 SSH 金鑰"""
    is_openlab = get_cluster_prefix() == "openlab"
    flow_desc = "Ansible ➔ Git" if is_openlab else "Ansible ➔ Storage ➔ Git"
    ui_header(f"🚀 [一鍵全自動] 依序輪換全網所有伺服器 SSH 金鑰 ({flow_desc})")
    ui_kv("受控伺服器範圍", "全網已納管伺服器 (All Managed Fleet Servers)")
    ui_kv("新私鑰發布端點", f"管理控制台與開發群組 ({target_nodes})")
    ui_divider()

    ui_info("👉 階段 1/3: 派發 Ansible SSH 自動化金鑰輪換...")
    if not rotate_ansible_keys(target_nodes):
        ui_warn("Ansible 金鑰輪換失敗或中斷，停止後續流程。")
        return False
    ui_success("✅ 階段 1/3 完成！")

    if not is_openlab:
        ui_divider()
        ui_info("👉 階段 2/3: 派發 儲存與設備 (Storage & Virtualization) SSH 金鑰輪換...")
        if not rotate_storage_keys(target_nodes):
            ui_warn("儲存與設備金鑰輪換失敗或中斷，停止後續流程。")
            return False
        ui_success("✅ 階段 2/3 完成！")

    ui_divider()
    step_num = "2/2" if is_openlab else "3/3"
    ui_info(f"👉 階段 {step_num}: 派發 Git 平台認證 SSH 金鑰輪換...")
    if not rotate_git_keys(target_nodes):
        ui_warn("Git 金鑰輪換失敗或中斷。")
        return False
    ui_success(f"✅ 階段 {step_num} 完成！")
    ui_divider()
    ui_success("🎉 全網所有伺服器與 Git 金鑰全套輪換完成！")
    return True


def interactive_menu():
    while True:
        from core.version import get_local_version
        local_ver = get_local_version()
        ui_header(f"OpenLabOps Cluster SSH Suite (lab-ssh v{local_ver})")
        ui_kv("控制端點", socket.gethostname() + (" [WSL 環境]" if is_wsl() else ""))
        ui_kv("工具版本", f"v{local_ver}")
        ui_divider()

        is_openlab = get_cluster_prefix() == "openlab"
        opt_all = "🚀 [一鍵全自動] 依序輪換所有伺服器 SSH 金鑰 (Ansible ➔ Git)" if is_openlab else "🚀 [一鍵全自動] 依序輪換所有伺服器 SSH 金鑰 (Ansible ➔ Storage ➔ Git)"
        opt_ansible = "🔑 派發 Ansible SSH 自動化金鑰輪換 (rotate-ansible-keys.yml)"
        opt_storage = "🔑 派發 儲存與設備專用金鑰輪換 (rotate-storage-keys.yml)"
        opt_git = "🔑 派發 Git 平台認證金鑰輪換 (rotate-git-keys.yml)"
        opt_host = "💻 本地生成當前端點 SSH 金鑰對並部署至伺服器 (支援 WSL 自動辨識)"
        opt_revoke = "🚫 派發清除特定端點公鑰 (revoke-host-key.yml)"
        opt_clean_auth = "🧹 稽核與清理全網 authorized_keys 殘留公鑰 (clean-authorized-keys.yml)"
        opt_sync_keys = "🔄 同步本機受控 SSH 管理金鑰 (~/.ssh/*.key)"
        opt_sync_cfg = "🔄 同步本機標準 ~/.ssh/config 連線別名設定"
        opt_exit = "❌ 退出 SSH 控制台"

        options = [opt_all, opt_ansible]
        if not is_openlab:
            options.append(opt_storage)
        options.extend([opt_git, opt_host, opt_revoke, opt_clean_auth, opt_sync_keys, opt_sync_cfg, opt_exit])

        choice_idx, selected_val = ui_select("請選取 SSH 維運項目:", options)

        if selected_val == opt_all:
            confirm_msg = "確定要依序輪換全網 Ansible 與 Git 金鑰？ (私鑰將自動發布至 dev 群組)" if is_openlab else "確定要依序輪換全網 Ansible、Storage 與 Git 金鑰？ (私鑰將自動發布至 dev 群組)"
            if ui_confirm(confirm_msg, "y"):
                rotate_all_server_keys("dev")
        elif selected_val == opt_ansible:
            if ui_confirm("確定要輪換全網 Ansible 金鑰？ (私鑰將自動發布至 dev 群組)", "y"):
                rotate_ansible_keys("dev")
        elif selected_val == opt_storage:
            if ui_confirm("確定要輪換 儲存與設備 (Storage & Virtualization) 金鑰？ (私鑰將自動發布至 dev 群組)", "y"):
                rotate_storage_keys("dev")
        elif selected_val == opt_git:
            if ui_confirm("確定要輪換 Git 認證金鑰？ (私鑰將自動發布至所有標準節點)", "y"):
                rotate_git_keys("all:!appliances")
        elif selected_val == opt_host:
            ep_name = get_default_endpoint_name()
            custom_name = input(f"請輸入端點名稱 (預設: {ep_name}): ").strip().lower() or ep_name
            k_path, p_path = generate_host_ssh_key(custom_name)
            if k_path and p_path:
                sync_p = sync_pub_to_secrets(custom_name, p_path)
                if ui_confirm(f"確定要將 [{custom_name}.pub] 套用至伺服器群 (servers) 的管理者帳號？", "y"):
                    apply_key_to_servers(custom_name, sync_p or p_path)
        elif selected_val == opt_revoke:
            from revoke_host_ssh_key import main as revoke_main
            revoke_main([])
        elif selected_val == opt_clean_auth:
            from clean_authorized_keys import dispatch_clean_authorized_keys
            if ui_confirm("確定要實際清理全網非白名單之 authorized_keys？（選 N 則僅執行 Dry-Run 稽核）", "n"):
                dispatch_clean_authorized_keys("all", dry_run=False)
            else:
                dispatch_clean_authorized_keys("all", dry_run=True)
        elif selected_val == opt_sync_keys:
            sync_ssh_keys()
        elif selected_val == opt_sync_cfg:
            sync_ssh_config()
        elif selected_val == opt_exit:
            ui_info("已退出 lab-ssh 控制台。")
            break


def main(args_list=None):
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="lab-ssh", description=t("ssh.cli_desc", "OpenLabOps SSH Management & Rotation Suite (lab-ssh)"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-a", "--rotate-all", action="store_true", help=t("ssh.cli_rotate_all", "Rotate all server SSH keys sequentially (Ansible, Storage, Git)"))
    parser.add_argument("--rotate-ansible", "--rotate-lab", action="store_true", help=t("ssh.cli_rotate_ansible", "Dispatch Ansible automation SSH key rotation"))
    parser.add_argument("--rotate-storage", "--rotate-openlab", action="store_true", help=t("ssh.cli_rotate_storage", "Dispatch Storage & Virtualization SSH key rotation"))
    parser.add_argument("--rotate-git", action="store_true", help=t("ssh.cli_rotate_git", "Dispatch Git platform SSH key rotation"))
    parser.add_argument("-t", "--target", type=str, default="control-node", help=t("ssh.cli_target", "Target endpoint for post-rotation key deployment (default: control-node)"))
    parser.add_argument("-g", "--gen-key", nargs="?", const="", help=t("ssh.cli_gen_key", "Generate local endpoint SSH key and deploy to servers (optional hostname)"))
    parser.add_argument("--sync-keys", action="store_true", help=t("ssh.cli_sync_keys", "Sync local managed SSH private and public keys"))
    parser.add_argument("--sync-config", action="store_true", help=t("ssh.cli_sync_config", "Sync standard ~/.ssh/config host aliases"))
    parser.add_argument("--revoke", type=str, help=t("ssh.cli_revoke", "Revoke SSH public key for the specified endpoint (e.g. --revoke laptop)"))
    parser.add_argument("--clean-auth-keys", action="store_true", help=t("ssh.cli_clean_auth", "Audit and clean stale/unauthorized keys from remote authorized_keys"))
    parser.add_argument("--apply", action="store_true", help=t("ssh.cli_apply", "Apply changes for --clean-auth-keys (default: dry-run)"))

    args = parser.parse_args(args_list)

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps SSH Suite (lab-ssh)")
        return

    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard(allow_readonly=False)

    if args.rotate_all:
        rotate_all_server_keys(args.target)
        return

    if args.rotate_ansible:
        rotate_ansible_keys(args.target)
        return

    if args.rotate_storage:
        rotate_storage_keys(args.target)
        return

    if args.rotate_git:
        rotate_git_keys(args.target if args.target != "control-node" else "all:!appliances")
        return

    if args.gen_key is not None:
        ep = args.gen_key.strip().lower() or get_default_endpoint_name()
        ui_header(f"產生端點主機 [{ep}] SSH 金鑰對並部署")
        k_path, p_path = generate_host_ssh_key(ep)
        if k_path and p_path:
            sync_p = sync_pub_to_secrets(ep, p_path)
            if ui_confirm(f"確定要將 [{ep}.pub] 部署至伺服器群 labadmin 帳號？", "y"):
                apply_key_to_servers(ep, sync_p or p_path)
        return

    if args.sync_keys:
        sync_ssh_keys()
        return

    if args.sync_config:
        sync_ssh_config()
        return

    if args.revoke:
        revoke_endpoint_key(args.revoke.strip().lower(), purge_secrets=True)
        return

    if args.clean_auth_keys:
        from clean_authorized_keys import dispatch_clean_authorized_keys
        dispatch_clean_authorized_keys(target_hosts=args.target if args.target != "control-node" else "all", dry_run=not args.apply)
        return

    interactive_menu()


if __name__ == "__main__":
    main()
