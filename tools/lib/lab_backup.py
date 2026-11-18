#!/usr/bin/env python3
"""
OpenLabOps Cluster Backup & Shared Config Deployment Suite (lab-backup)
負責全網 Gateway 防火牆/DNS 備份、
以及本機組態備份並廣播共用變更至全網 (Console Shared Config Broadcast / Family Deploy)。
"""

import os
import sys
import socket
import argparse
import subprocess

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_select, ui_confirm
from core.config import get_cluster_prefix, is_openlab
from core.version import get_local_version
from core.gitea_api import gitea_dispatch


def trigger_gateway_backup() -> bool:
    """觸發 Gateway 防火牆與 DNS 組態備份"""
    if get_cluster_prefix() == "openlab":
        ui_info("OpenLabOps 環境不支援專用網關備份（特化網關已排除）。")
        return True
    ui_info("正在派發 Gateway 防火牆與 DNS 組態備份工作流 (backup-gateway-config.yml)...")
    success = gitea_dispatch("backup-gateway-config.yml", {"ref": "main"})
    if success:
        ui_success("Gateway 組態備份完成！")
    return success


def trigger_sync_and_broadcast_config(source_host: str = None) -> bool:
    """
    Console Family Change Deploy (採集本機組態並廣播共用變更)
    採集當前主機組態至 openlab-configs：
    - 若檢測到全域/共用家族組態 (openlab.*, .vimrc, editor/* 等) 變更，自動透過 Ansible 廣播套用至全網節點！
    - 若僅為本機特有組態，則僅完成雲端備份。
    """
    if not source_host:
        source_host = socket.gethostname().split('.')[0].lower()

    ui_info(f"正在派發組態採集與共用廣播工作流 (來源端點: {source_host})...")
    payload = {
        "ref": "main",
        "inputs": {
            "source_host": source_host
        }
    }
    success = gitea_dispatch("sync-node-config.yml", payload)
    if success:
        ui_success(f"已成功觸發 sync-node-config 工作流！Gitea Runner 正在對 [{source_host}] 執行組態採集與共用廣播。")
    return success


def run_full_backup_suite(source_host: str = None) -> bool:
    """一鍵執行全套備份"""
    is_openlab = get_cluster_prefix() == "openlab"
    ui_header("💾 [一鍵全套備份] 節點備份與共用組態廣播")
    ui_divider()

    if not is_openlab:
        ui_info("👉 階段 1/2: 執行 Gateway 防火牆與 DNS 組態備份...")
        trigger_gateway_backup()
        ui_divider()

    step_desc = "階段 1/1" if is_openlab else "階段 2/2"
    ui_info(f"👉 {step_desc}: 採集本機組態並廣播共用變更至全網...")
    trigger_sync_and_broadcast_config(source_host)
    ui_divider()

    ui_success("✨ 叢集全套備份與共用組態同步執行完畢！")
    return True


def trigger_selective_node_backup() -> bool:
    """透過階層選單與 Checklist 挑選節點並透過 Gitea Actions 派發組態採集與備份工作流 [AGENTS.md §3.9]"""
    from core.ui_menu import select_target_hosts
    targets = select_target_hosts("請選擇欲備份組態檔案之目標節點", default_all=True)
    if not targets:
        ui_warn("未選取任何節點，取消備份。")
        return False
    target_str = ",".join(targets)
    ui_info(f"正在向 Gitea Actions 派發選定節點 [{target_str}] 之組態採集與備份工作流 (sync-node-config.yml)...")
    all_ok = True
    for host in targets:
        if not gitea_dispatch("sync-node-config.yml", {"ref": "main", "inputs": {"source_host": host}}):
            all_ok = False
    if all_ok:
        ui_success(f"已成功觸發選定節點 [{target_str}] 之組態備份工作流！")
    return all_ok


def interactive_menu():
    while True:
        from core.version import get_local_version
        local_ver = get_local_version()
        current_host = socket.gethostname().split('.')[0].lower()
        ui_header(f"OpenLabOps Cluster Backup Suite (lab-backup v{local_ver})")
        ui_kv("目前主機", current_host)
        ui_kv("工具版本", f"v{local_ver}")
        ui_divider()

        is_openlab = get_cluster_prefix() == "openlab"
        opt_all = "🚀 [一鍵全套備份] 依序執行節點備份與本機共用組態廣播"
        opt_select = "🗄️ [自選節點備份] 透過階層選單挑選目標節點備份組態 (Checklist)"
        opt_broadcast = f"🔄 採集本機 [{current_host}] 組態並廣播共用變更至全網 (Family Deploy)"
        opt_gw = "🛡️ 備份 Gateway 防火牆規則與 DNS 組態 (backup-gateway-config.yml)"
        opt_pull = "📦 觸發 Docker Compose 全網節點 Pull 同步 (pull-docker-compose.yml)"
        opt_exit = "❌ 退出 Backup 控制台"

        options = [opt_all, opt_select, opt_broadcast]
        if not is_openlab:
            options.append(opt_gw)
        options.extend([opt_pull, opt_exit])

        choice_idx, selected_val = ui_select("請選取備份/組態廣播項目:", options)

        if selected_val == opt_all:
            confirm_msg = "確定要執行全套備份？" if is_openlab else "確定要執行全套備份 (閘道備份 + 本機共用組態廣播)？"
            if ui_confirm(confirm_msg, "y"):
                run_full_backup_suite(current_host)
        elif selected_val == opt_select:
            trigger_selective_node_backup()
        elif selected_val == opt_broadcast:
            if ui_confirm(f"確定要自本機 [{current_host}] 採集最新組態並向全網廣播共用變更？", "y"):
                trigger_sync_and_broadcast_config(current_host)
        elif selected_val == opt_gw:
            if ui_confirm("確定要觸發 Gateway 防火牆與 DNS 組態備份？", "y"):
                trigger_gateway_backup()
        elif selected_val == opt_pull:
            if ui_confirm("確定要觸發節點上的 Docker Compose 同步？", "y"):
                gitea_dispatch("pull-docker-compose.yml", {"ref": "main"})
        elif selected_val == opt_exit:
            ui_info("已退出 lab-backup 控制台。")
            break


def main(args_list=None):
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="lab-backup", description=t("backup.cli_desc", "OpenLabOps Cluster Backup & Shared Config Suite (lab-backup)"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-a", "--all", action="store_true", help=t("backup.cli_all", "Run gateway backup and broadcast shared local configs"))
    parser.add_argument("-g", "--gateway", action="store_true", help=t("backup.cli_gateway", "Backup Gateway firewall and DNS configs"))
    parser.add_argument("-b", "--broadcast", "--family-deploy", action="store_true", help=t("backup.cli_broadcast", "Collect local configs and broadcast shared changes across fleet"))
    parser.add_argument("-s", "--source", type=str, help=t("backup.cli_source", "Specify source host for config collection (default: localhost)"))

    args = parser.parse_args(args_list)

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Backup Suite (lab-backup)")
        return

    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard(allow_readonly=False)

    source_host = args.source or socket.gethostname().split('.')[0].lower()

    if args.all:
        if not run_full_backup_suite(source_host):
            sys.exit(1)
        return

    if args.gateway:
        if not trigger_gateway_backup():
            sys.exit(1)
        return

    if args.broadcast:
        if not trigger_sync_and_broadcast_config(source_host):
            sys.exit(1)
        return

    interactive_menu()


if __name__ == "__main__":
    main()
