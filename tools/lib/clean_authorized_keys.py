#!/usr/bin/env python3
"""
OpenLabOps Tool: Authorized Keys Audit & Cleanup (clean-authorized-keys)
比對機密庫 (secrets/ssh-key/*.pub) 白名單，稽核並清理各節點 authorized_keys 中之過期、重複或未授權公鑰。
"""

import os
import sys
import argparse

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_confirm
from core.gitea_api import gitea_dispatch


def dispatch_clean_authorized_keys(target_hosts: str = "all", dry_run: bool = True) -> bool:
    """派發 Gitea Actions 工作流執行 authorized_keys 稽核與清理"""
    mode_label = "稽核預覽 (Dry-Run)" if dry_run else "實際清除 (Apply)"
    ui_info(f"正在向 Gitea Actions 派發 authorized_keys {mode_label} (目標: {target_hosts})...")
    return gitea_dispatch("clean-authorized-keys.yml", {
        "ref": "main",
        "inputs": {
            "target_hosts": target_hosts,
            "dry_run": "true" if dry_run else "false",
        }
    })


def main(args_list=None):
    from core.i18n import t
    parser = argparse.ArgumentParser(
        prog="clean-authorized-keys",
        description=t("clean_auth.cli_desc", "Audit and clean stale or unauthorized keys from remote authorized_keys"),
    )
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-t", "--target", type=str, default="all", help=t("clean_auth.cli_target", "Target host(s) or Ansible group (default: all)"))
    parser.add_argument("--apply", action="store_true", help=t("clean_auth.cli_apply", "Apply changes and remove stale/unauthorized keys (default: dry-run)"))
    parser.add_argument("-y", "--yes", action="store_true", help=t("clean_auth.cli_yes", "Skip confirmation prompt when using --apply"))

    args = parser.parse_args(args_list)

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Authorized Keys Cleanup Tool")
        return

    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard(allow_readonly=not args.apply)

    dry_run = not args.apply
    ui_header("🧹 全網 authorized_keys 稽核與清理工具")
    ui_kv("目標節點範圍", args.target)
    ui_kv("執行模式", "稽核預覽 (Dry-Run，不修改檔案)" if dry_run else "實際清除 (Apply，保留白名單公鑰並移除其餘條目)")
    ui_divider()

    if not dry_run and not args.yes:
        if not ui_confirm(f"確定要實際清理 [{args.target}] 上非白名單之 authorized_keys 條目？", "n"):
            ui_warn("操作已取消。")
            return

    if not dispatch_clean_authorized_keys(target_hosts=args.target, dry_run=dry_run):
        sys.exit(1)


if __name__ == "__main__":
    main()
