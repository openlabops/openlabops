#!/usr/bin/env python3
"""
OpenLabOps Node Information, Audit & Workspace Sync Suite (lab-info)
負責派發全網節點手冊巡檢 (update-node-docs.yml)、更新 openlab-configs 遠端倉庫、
自動在本地 Antigravity workspace (/home/labadmin/openlab-configs) 執行 Git Pull 同步，
並將 JSON 資料渲染為 Obsidian Markdown 節點手冊。
"""

import os
import sys
import socket
import subprocess
import argparse

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_select, ui_confirm
from core.gitea_api import gitea_dispatch
from core.config import get_path, get_node_info_dir, get_cache_dir, TOOLS_ROOT
from core.version import get_local_version

dev_configs = TOOLS_ROOT.parent / "openlab-configs"
WORKSPACE_CONFIGS_DIR = os.environ.get("WORKSPACE_CONFIGS_DIR", str(dev_configs) if dev_configs.exists() else "")
NODE_INFO_DIR = str(get_node_info_dir())
DEFAULT_DOCS_OUT = str(get_cache_dir() / "docs")
VAULT_OUT_DIR = os.environ.get("OBSIDIAN_VAULT_DIR", DEFAULT_DOCS_OUT)


def dispatch_node_docs_update() -> bool:
    """向 Gitea Actions 派發 update-node-docs.yml 進行全網巡檢並 push 至 openlab-configs"""
    ui_info("正在向 Gitea Actions 派發 update-node-docs.yml (全網節點即時巡檢)...")
    success = gitea_dispatch("update-node-docs.yml", {"ref": "main"})
    if success:
        ui_success("Gitea Runner 巡檢完成，最新 node-information 已推送至 openlab-configs 遠端倉庫！")
    return success


def pull_local_workspace_configs() -> bool:
    """在本地 Antigravity workspace (openlab-configs) 執行 git pull origin main 同步（若為本地開發模式）"""
    if not WORKSPACE_CONFIGS_DIR or not os.path.exists(WORKSPACE_CONFIGS_DIR):
        ui_info("非本地開發工作區模式（未偵測到 openlab-configs git 倉庫），略過本機 Git Pull。")
        return True

    ui_info(f"正在本地工作區 [{WORKSPACE_CONFIGS_DIR}] 執行 Git Pull 同步...")
    try:
        res = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=WORKSPACE_CONFIGS_DIR,
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            ui_success(f"工作區已同步至最新進度！\n  └─ {res.stdout.strip()}")
            return True
        else:
            ui_warn(f"Git Pull 警告或錯誤: {res.stderr.strip()}")
            return False
    except Exception as e:
        ui_error(f"執行 Git Pull 時發生異常: {e}")
        return False


def render_markdown_docs(out_dir: str = VAULT_OUT_DIR) -> bool:
    """將本地 node-information JSON 轉出為 Markdown"""
    if not os.path.exists(NODE_INFO_DIR):
        ui_warn(f"找不到 node-information 目錄: {NODE_INFO_DIR}")
        return False

    render_script = os.path.join(LIB_DIR, "render_node_doc.py")
    ui_info(f"正在渲染 JSON 資料為 Markdown 至目標路徑: {out_dir}...")
    try:
        res = subprocess.run(
            [sys.executable, render_script, NODE_INFO_DIR, "--out-dir", out_dir],
            check=False
        )
        if res.returncode == 0:
            ui_success(f"節點手冊 Markdown 轉出成功！")
            return True
        else:
            ui_warn(f"渲染過程發生部分警告，回傳碼: {res.returncode}")
            return False
    except Exception as e:
        ui_error(f"渲染 Markdown 異常: {e}")
        return False


def run_full_sync_cycle() -> bool:
    """執行全流程：遠端巡檢 ➔ 本機工作區 Pull ➔ Markdown 渲染"""
    ui_header("📝 全網節點資訊採集、工作區同步與手冊渲染 (Full Cycle)")
    ui_divider()

    # 1. 遠端 Actions 巡檢採集
    ui_info("👉 步驟 1/3: 派發遠端 Gitea Actions 巡檢節點...")
    if not dispatch_node_docs_update():
        ui_warn("遠端巡檢任務未順利完成，後續同步可能非最新資料。")
    ui_divider()

    # 2. 本地工作區 Pull
    ui_info("👉 步驟 2/3: 同步本地 openlab-configs 工作區...")
    pull_local_workspace_configs()
    ui_divider()

    # 3. 渲染 Markdown
    ui_info("👉 步驟 3/3: 渲染 Obsidian 筆記庫 Markdown 節點手冊...")
    render_markdown_docs()
    ui_divider()

    ui_success("✨ lab-info 全套流程執行完畢！所有節點手冊已與叢集最新現狀同步。")
    return True


def interactive_menu():
    while True:
        from core.version import get_local_version
        local_ver = get_local_version()
        ui_header(f"OpenLabOps Node Info & Docs Suite (lab-info v{local_ver})")
        ui_kv("本機工作區", WORKSPACE_CONFIGS_DIR or "(API/Cache 獨立模式)")
        ui_kv("手冊渲染輸出", VAULT_OUT_DIR)
        ui_divider()

        options = [
            "🚀 [一鍵全流程] 遠端全網巡檢 ➔ 本地工作區 Pull ➔ 渲染 Markdown 手冊",
            "🌐 僅派發 Gitea Actions 執行全網伺服器狀態巡檢 (update-node-docs.yml)",
            "📥 僅在本地 openlab-configs 執行 Git Pull 同步",
            "📄 僅依據本地 node-information JSON 轉出 Markdown 手冊",
            "❌ 退出 Info 控制台"
        ]

        choice_idx, selected_val = ui_select("請選取節點資訊操作項目:", options)

        if choice_idx == 1:
            if ui_confirm("確定要執行完整的「遠端巡檢 ➔ 工作區 Pull ➔ 手冊渲染」流程？", "y"):
                run_full_sync_cycle()
        elif choice_idx == 2:
            if ui_confirm("確定要觸發遠端伺服器巡檢任務？", "y"):
                dispatch_node_docs_update()
        elif choice_idx == 3:
            pull_local_workspace_configs()
        elif choice_idx == 4:
            render_markdown_docs()
        elif choice_idx == 5:
            ui_info("已退出 lab-info 控制台。")
            break


def main(args_list=None):
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="lab-info", description=t("info.cli_desc", "OpenLabOps Node Information & Workspace Sync Suite (lab-info)"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-a", "--all", action="store_true", help=t("info.cli_all", "Run remote audit, pull workspace, and render Markdown"))
    parser.add_argument("-d", "--dispatch-only", action="store_true", help=t("info.cli_dispatch", "Only dispatch Gitea Actions audit workflow"))
    parser.add_argument("-p", "--pull-only", action="store_true", help=t("info.cli_pull", "Only pull local openlab-configs workspace"))
    parser.add_argument("-r", "--render-only", action="store_true", help=t("info.cli_render", "Only render Markdown manuals from local JSON"))

    args = parser.parse_args(args_list)

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Node Info Suite (lab-info)")
        return

    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard(allow_readonly=bool(args.pull_only or args.render_only))

    if args.dispatch_only:
        if not dispatch_node_docs_update():
            sys.exit(1)
        return

    if args.pull_only:
        pull_local_workspace_configs()
        return

    if args.render_only:
        render_markdown_docs()
        return

    if args.all:
        run_full_sync_cycle()
        return

    # 若無參數，預設提供互動式選單
    interactive_menu()


if __name__ == "__main__":
    main()
