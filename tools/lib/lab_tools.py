#!/usr/bin/env python3
"""
OpenLabOps Cluster Management Console (lab-tools)
叢集總維運儀表板與頂層控制台，統合調用五大專業模組套件：
- lab-setup : 伺服器初建、基線設定與全節點 IaC 套用
- lab-ssh   : 叢集管理金鑰輪換、端點金鑰生成/撤銷與客戶端同步
- lab-info  : 節點手冊巡檢、遠端 Push、本地工作區 Git Pull 與 Markdown 渲染
- lab-backup: 叢集備份、Gateway 備份與共用組態全網廣播 (Family Deploy)
"""

import os
import sys
import platform
import socket
import time
import subprocess
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import (
    ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error,
    C_GREEN, C_RED, C_YELLOW, C_RESET
)
from core.ui_menu import ui_select, ui_confirm, ui_spinner
from core.ui_curses import is_tui_supported, CursesTUI, run_tui
from core.gitea_api import gitea_dispatch, load_gitea_token
from core.config import is_openlab
from core.lockout import enforce_lockout_guard
from core.i18n import t, get_locale, set_locale


def trigger_sync_packages(target_hosts: str = "servers", apply_sync: bool = False):
    ui_info(f"正在向 Gitea Actions 派發 IaC 套件清冊比對工作流 (目標: {target_hosts}, 寫入模式: {apply_sync})...")
    payload = {
        "ref": "main",
        "inputs": {
            "target_hosts": target_hosts,
            "apply_sync": "true" if apply_sync else "false"
        }
    }
    success = gitea_dispatch("sync-package-inventory.yml", payload)
    if success:
        ui_success("已成功手動派發 sync-package-inventory 工作流！")
    return success


def run_local_connectivity_test() -> bool:
    """在當前控制台直接對全網節點執行原生 SSH / TCP 活體連通性檢測 (100% Python 標準庫 [INV-01])。"""
    from lab_node import get_current_snapshot
    from concurrent.futures import ThreadPoolExecutor

    ui_header("全網節點與服務即時連通性檢測 (Local Native Probe)")
    nodes = get_current_snapshot()
    if not nodes:
        ui_warn("目前尚未有任何已納管節點事實。請先執行 `lab-node add <IP>` 納管節點。")
        return True

    ui_info(f"正在對 {len(nodes)} 台已納管節點進行並行連通性探測...")
    print("-" * 76)
    print(f"{'主機名稱':<14} {'主要 IP':<18} {'TCP (22)':<16} {'SSH 免密認證'}")
    print("-" * 76)

    def _test_single(n):
        hname = n.get("hostname", "unknown")
        ip = n.get("primary_ip") or n.get("ansible_host") or n.get("ip") or ""
        port = int(n.get("ssh_port") or n.get("port") or 22)
        target_user = n.get("ansible_user") or n.get("target_user")
        if not target_user:
            target_user = "ansible" if is_openlab() else "lab"

        app_type = n.get("appliance_type", "none")
        login_user = target_user

        tcp_ok = False
        ssh_ok = False

        if ip:
            try:
                s = socket.create_connection((ip, port), timeout=2.0)
                s.close()
                tcp_ok = True
            except Exception:
                tcp_ok = False

        if tcp_ok and ip:
            cmd = [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=3",
                "-p", str(port),
            ]
            ssh_dir = Path.home() / ".ssh"
            key_candidates = [
                ssh_dir / f"{target_user}.key",
                ssh_dir / "ansible.key",
                ssh_dir / "ansible.key",
                ssh_dir / "id_user.key",
            ]
            if app_type == "kvm":
                key_candidates.insert(0, ssh_dir / "ansible.key")
            for k in key_candidates:
                if k.exists():
                    cmd.extend(["-i", str(k)])
                    break

            cmd.extend([f"{login_user}@{ip}", "true"])
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ssh_ok = (r.returncode == 0)

        return hname, ip, tcp_ok, ssh_ok

    with ThreadPoolExecutor(max_workers=min(16, max(len(nodes), 1))) as executor:
        results = list(executor.map(_test_single, nodes))

    all_online = True
    for hname, ip, tcp_ok, ssh_ok in results:
        tcp_badge = f"{C_GREEN}● 連通{C_RESET}" if tcp_ok else f"{C_RED}○ 斷線{C_RESET}"
        if ssh_ok:
            ssh_badge = f"{C_GREEN}[✓] 免密登入成功{C_RESET}"
        elif tcp_ok:
            ssh_badge = f"{C_YELLOW}[!] 需密碼或金鑰拒絕{C_RESET}"
            all_online = False
        else:
            ssh_badge = f"{C_RED}[✗] 主機無回應{C_RESET}"
            all_online = False
        print(f"{hname:<14} {ip:<18} {tcp_badge:<22} {ssh_badge}")

    print("-" * 76)
    if all_online:
        ui_success(f"全網共 {len(nodes)} 台節點連通性探測完畢，全數在線受控！")
    else:
        ui_warn("連通性探測完畢，部分節點離線或金鑰認證受阻。")
    return all_online


def trigger_connectivity_test(fallback_local: bool = True) -> bool:
    ui_info("正在向 Gitea Actions 派發全網節點與服務連通性檢測 (test-connectivity.yml)...")
    success = gitea_dispatch("test-connectivity.yml", {"ref": "main"})
    if success:
        ui_success("全網連通性測試已派發至 Gitea！")
        return True

    if fallback_local:
        if ui_confirm("Gitea 派發失敗，是否改在當前本地直接探測節點連通性？", "y"):
            return run_local_connectivity_test()
    return False


def main():
    # 支援子套件命令列轉發
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        sub_args = sys.argv[2:]

        if cmd in ("status", "lab-status"):
            from lab_status import main as status_main
            sys.argv = [sys.argv[0]] + sub_args
            status_main()
            return

        if cmd in ("setup", "lab-setup"):
            from lab_setup import main as setup_main
            setup_main(sub_args)
            return

        if cmd in ("ssh", "lab-ssh", "keys"):
            from lab_ssh import main as ssh_main
            ssh_main(sub_args)
            return

        if cmd in ("info", "lab-info", "docs"):
            from lab_info import main as info_main
            info_main(sub_args)
            return

        if cmd in ("backup", "lab-backup"):
            from lab_backup import main as backup_main
            backup_main(sub_args)
            return

        if cmd in ("upgrade", "lab-upgrade"):
            from lab_upgrade import main as upgrade_main
            sys.argv = [sys.argv[0]] + sub_args
            upgrade_main()
            return

        if cmd in ("node", "lab-node", "enroll"):
            from lab_node import main as node_main
            sys.argv = [sys.argv[0]] + sub_args
            node_main()
            return

        if cmd in ("config", "lab-config"):
            from lab_config import main as config_main
            sys.argv = [sys.argv[0]] + sub_args
            config_main()
            return

        if cmd in ("sync", "sync-config", "broadcast-config", "family-deploy"):
            from lab_backup import trigger_sync_and_broadcast_config
            target_host = sub_args[0] if sub_args else socket.gethostname().split('.')[0].lower()
            trigger_sync_and_broadcast_config(target_host)
            return

        if cmd in ("sync-iac", "sync-packages", "audit-packages"):
            target_hosts = sub_args[0] if sub_args else "servers"
            trigger_sync_packages(target_hosts, apply_sync=False)
            return

        if cmd in ("test", "connectivity", "test-connectivity"):
            trigger_connectivity_test()
            return

        if cmd in ("sync-ssh-config", "ssh-config"):
            from sync_ssh_config import sync_ssh_config
            sync_ssh_config()
            return

        if cmd in ("sync-keys", "sync-ssh-keys"):
            from sync_ssh_keys import sync_ssh_keys
            sync_ssh_keys()
            return

        if cmd in ("update-tools", "sync-tools", "self-update"):
            from sync_ops_tools import update_tools_from_gitea
            update_tools_from_gitea()
            return

        if cmd in ("inspect-run", "run-error", "log"):
            if sub_args and sub_args[0].isdigit():
                from core.gitea_api import display_run_error_feedback
                display_run_error_feedback(int(sub_args[0]))
            else:
                ui_warn("請提供欲查詢之 Action Run ID (例如: lab-tools inspect-run 75)")
            return

        if cmd in ("revoke", "revoke-key"):
            if sub_args:
                from revoke_host_ssh_key import revoke_endpoint_key
                revoke_endpoint_key(sub_args[0].strip().lower(), purge_secrets=True)
            else:
                ui_warn("請提供欲清除之端點主機名稱 (例如: lab-tools revoke laptop)")
            return

        if cmd in ("-v", "--version", "version"):
            from core.version import print_version
            print_version("OpenLabOps Cluster Management Console (lab-tools)")
            return

        if cmd in ("-h", "--help", "help"):
            from core.version import get_local_version
            ver = get_local_version()
            print(f"""OpenLabOps Cluster Management Console (lab-tools v{ver})
五大專業套件與叢集頂層維運控制台

使用方式:
  lab-tools [指令] [參數...]

子套件進入點:
  setup, lab-setup    伺服器初建、基線設定與全節點 IaC 套用
  ssh, lab-ssh        叢集管理金鑰輪換、端點金鑰生成/撤銷與客戶端同步
  info, lab-info      節點手冊巡檢、遠端 Push、工作區 Git Pull 與 Markdown 渲染
  backup, lab-backup  叢集備份、Gateway 備份與共用組態全網廣播

獨立捷徑指令:
  sync, broadcast      採集本機組態並廣播共用變更至全網 (Family Deploy)
  sync-iac             比對節點套件與 Ansible host_vars IaC 狀態
  test, connectivity   派發全網節點 SSH 與服務連通性檢測
  sync-ssh-config      同步本機 ~/.ssh/config 連線別名
  sync-keys            同步本機受控 SSH 管理私鑰與公鑰
  inspect-run <ID>     查詢 Gitea Actions 指定 Run 之錯誤診斷與日誌
  revoke <hostname>    全網清除指定端點之 SSH 公鑰
  update-tools         自 Gitea 伺服器同步並升級本地工具鏈

常用選項:
  --plain, --no-tui    強制使用傳統純文字序列式互動選單 (適用於指令稿、Agent 或不支援 Curses 之終端)
  -v, --version        顯示版本號
  -h, --help           顯示此說明資訊

若未提供參數且終端機支援，預設啟動雙欄現代化 Curses TUI 儀表板控制台。
""")
            return

        if cmd in ("--plain", "--no-tui", "--batch", "-b", "--non-interactive"):
            linear_interactive_menu()
            return

        ui_error(f"Unknown command or option: {sys.argv[1]} (Run `lab-tools --help` for usage)")
        sys.exit(2)

    # 若未提供參數，檢查是否支援現代化 Curses TUI
    if is_tui_supported():
        try:
            launch_curses_tui()
            return
        except Exception as e:
            # 發生任何例外，自動降級為傳統文字選單
            ui_warn(f"Curses TUI 啟動異常 ({e})，自動降級至傳統文字選單...")
            linear_interactive_menu()
            return
    else:
        # 非人類終端、無 TTY、CI/CD 或設定了 --plain 時直接進入傳統序列式選單
        linear_interactive_menu()


def launch_curses_tui():
    """啟動 100% Python 原生標準庫雙欄現代化 Curses TUI 儀表板。"""
    from core.version import get_local_version
    local_ver = get_local_version()

    tui = CursesTUI(
        title=t("tools.tui_title", f"OpenLabOps Cluster Management Console (v{local_ver})"),
        subtitle=t("tools.tui_subtitle", f"主機: {socket.gethostname()} | 核心: {platform.system()} {platform.release()}", host=socket.gethostname(), kernel=f"{platform.system()} {platform.release()}")
    )

    # 1. 📊 叢集即時狀態
    def _act_status_full():
        from lab_status import main as status_main
        sys.argv = ["lab-status"]
        status_main()

    def _act_status_keys():
        from lab_status import main as status_main
        sys.argv = ["lab-status", "-k"]
        status_main()

    def _act_upgrade():
        from lab_upgrade import upgrade_cluster
        upgrade_cluster()

    tui.add_category(
        t("tools.cat_status", "📊 叢集即時狀態"),
        t("tools.cat_status_desc", "全網節點健康指標、金鑰生命週期與套件維護"),
        [
            {"name": t("tools.act_status_full", "lab-status 完整儀表板"), "desc": t("tools.act_status_full_desc", "顯示全網節點在線狀態、CPU/記憶體負載與容器"), "action": _act_status_full},
            {"name": t("tools.act_status_keys", "lab-status 金鑰審計 (-k)"), "desc": t("tools.act_status_keys_desc", "零信任 SSH 授權清冊與 90 天金鑰到期預警"), "action": _act_status_keys},
            {"name": t("tools.act_upgrade", "lab-upgrade 叢集套件更新"), "desc": t("tools.act_upgrade_desc", "跨發行版自動化套件升級巡檢與重開機提醒"), "action": _act_upgrade},
        ]
    )

    # 2. 🖥️ 伺服器巡檢與手冊
    def _act_info_full():
        from lab_info import run_full_sync_cycle
        run_full_sync_cycle()

    def _act_info_menu():
        from lab_info import interactive_menu as info_menu
        info_menu()

    def _act_node_menu():
        from lab_node import interactive_menu as node_menu
        node_menu()

    tui.add_category(
        t("tools.cat_info", "🖥️ 伺服器巡檢與手冊"),
        t("tools.cat_info_desc", "節點硬體遙測事實採集、Obsidian 渲染與節點納管"),
        [
            {"name": t("tools.act_info_full", "lab-info 一鍵巡檢與渲染"), "desc": t("tools.act_info_full_desc", "遠端採集遙測 ➔ 工作區 Pull ➔ 渲染 Obsidian Markdown"), "action": _act_info_full},
            {"name": t("tools.act_info_menu", "lab-info 獨立巡檢選單"), "desc": t("tools.act_info_menu_desc", "單項遠端巡檢、本機工作區同步與 Markdown 手冊轉出"), "action": _act_info_menu},
            {"name": t("tools.act_node_menu", "lab-node 節點動態納管"), "desc": t("tools.act_node_menu_desc", "自動引導註冊新伺服器、產生 host_vars 與規格事實"), "action": _act_node_menu},
        ]
    )

    # 3. 🔑 SSH 金鑰生命週期
    def _act_ssh_rotate_all():
        from lab_ssh import rotate_all_server_keys
        rotate_all_server_keys(target_nodes="dev")

    def _act_ssh_menu():
        from lab_ssh import interactive_menu as ssh_menu
        ssh_menu()

    def _act_sync_ssh_config():
        from sync_ssh_config import sync_ssh_config
        sync_ssh_config()

    def _act_sync_ssh_keys():
        from sync_ssh_keys import sync_ssh_keys
        sync_ssh_keys()

    tui.add_category(
        t("tools.cat_ssh", "🔑 SSH 金鑰生命週期"),
        t("tools.cat_ssh_desc", "三階段安全金鑰輪換、端點公鑰佈署與別名同步"),
        [
            {"name": t("tools.act_ssh_rotate_all", "一鍵依序輪換所有伺服器金鑰"), "desc": t("tools.act_ssh_rotate_all_desc", "依序輪換 Lab ➔ OpenLabOps ➔ Git 並自動部署至端點"), "action": _act_ssh_rotate_all},
            {"name": t("tools.act_ssh_menu", "lab-ssh 獨立金鑰管理選單"), "desc": t("tools.act_ssh_menu_desc", "單項金鑰輪換、端點金鑰生成/撤銷與金鑰部署"), "action": _act_ssh_menu},
            {"name": t("tools.act_sync_ssh_config", "sync-ssh-config 同步連線別名"), "desc": t("tools.act_sync_ssh_config_desc", "依據 CMDB 拓撲自動更新 ~/.ssh/config"), "action": _act_sync_ssh_config},
            {"name": t("tools.act_sync_ssh_keys", "sync-ssh-keys 同步本機受控金鑰"), "desc": t("tools.act_sync_ssh_keys_desc", "自管理庫同步 0600 受控 SSH 私鑰至本機"), "action": _act_sync_ssh_keys},
        ]
    )

    # 4. ⚙️ IaC 與配置管理
    def _act_iac_audit():
        trigger_sync_packages(apply_sync=False)

    def _act_iac_apply():
        trigger_sync_packages(apply_sync=True)

    def _resolve_ansible_paths():
        candidates = [
            Path(LIB_DIR).parent.parent / "ansible",
            Path.home() / "openlabops" / "ansible",
            Path.home() / "openlab-ansible",
            Path.home() / "openlabops" / "ansible",
        ]
        for c in candidates:
            p = c / "playbooks" / "sync-package-inventory.yml"
            i = c / "inventory" / "hosts.yml"
            if p.exists() and i.exists():
                return str(p), str(i)
        return None, None

    def _act_iac_local():
        enforce_lockout_guard()
        ansible_play, ansible_inv = _resolve_ansible_paths()
        if ansible_play and os.path.exists(ansible_play):
            subprocess.run(["ansible-playbook", "-i", ansible_inv, ansible_play])
        else:
            ui_warn("找不到本地 Ansible 劇本 (sync-package-inventory.yml)")

    def _act_config_menu():
        from lab_config import main as config_main
        config_main([])

    def _act_setup_full():
        target_hosts = input("請輸入目標伺服器群組 (預設: servers): ").strip() or "servers"
        from lab_setup import run_full_system_setup
        run_full_system_setup(target_hosts)

    def _act_setup_menu():
        from lab_setup import ServerSetupRegistry, interactive_menu as setup_menu
        setup_menu(ServerSetupRegistry())

    tui.add_category(
        t("tools.cat_iac", "⚙️ IaC 與配置管理"),
        t("tools.cat_iac_desc", "軟體套件清冊比對、宣告式漂移收斂與系統基線更新"),
        [
            {"name": t("tools.act_iac_audit", "IaC 套件漂移檢查 (Audit Only)"), "desc": t("tools.act_iac_audit_desc", "比對主機手動安裝套件與 host_vars，產出漂移報告"), "action": _act_iac_audit},
            {"name": t("tools.act_iac_apply", "IaC 套件現況同步 (Apply Sync)"), "desc": t("tools.act_iac_apply_desc", "採集主機現況直接回寫 host_vars 完成宣告收斂"), "action": _act_iac_apply},
            {"name": t("tools.act_iac_local", "本地互動式 Ansible 套件比對"), "desc": t("tools.act_iac_local_desc", "在當前終端機逐項互動確認是否加入 host_vars"), "action": _act_iac_local},
            {"name": t("tools.act_config_menu", "lab-config 宣告式組態管理"), "desc": t("tools.act_config_menu_desc", "與遠端 Gitea 比對、檢視 Diff 並推送本機組態 (GitOps)"), "action": _act_config_menu},
            {"name": t("tools.act_setup_full", "lab-setup 全網基線更新"), "desc": t("tools.act_setup_full_desc", "套用 system-base-setup 包含使用者、SSH、網路與基線"), "action": _act_setup_full},
            {"name": t("tools.act_setup_menu", "lab-setup 獨立初建選單"), "desc": t("tools.act_setup_menu_desc", "細部設定精靈與個別伺服器模組微調"), "action": _act_setup_menu},
        ]
    )

    # 5. 💾 備份與災難復原
    def _act_backup_suite():
        current_host = socket.gethostname().split('.')[0].lower()
        from lab_backup import run_full_backup_suite
        run_full_backup_suite(current_host)

    def _act_backup_menu():
        from lab_backup import interactive_menu as backup_menu
        backup_menu()

    tui.add_category(
        t("tools.cat_backup", "💾 備份與災難復原"),
        t("tools.cat_backup_desc", "網關組態備份、本機組態採集與全網廣播 (Family Deploy)"),
        [
            {"name": t("tools.act_backup_suite", "一鍵備份與共用組態廣播"), "desc": t("tools.act_backup_suite_desc", "備份 Gateway 並採集本機組態廣播全網"), "action": _act_backup_suite},
            {"name": t("tools.act_backup_menu", "lab-backup 獨立備份選單"), "desc": t("tools.act_backup_menu_desc", "單獨備份網關、單獨廣播組態或還原伺服器"), "action": _act_backup_menu},
        ]
    )

    # 6. 🛠️ 系統維護自檢
    def _act_connectivity_local():
        run_local_connectivity_test()

    def _act_connectivity_gitea():
        trigger_connectivity_test()

    def _act_inspect_runs():
        from core.gitea_api import get_action_runs, display_run_error_feedback
        ui_info("正在查詢 Gitea Actions 最近執行紀錄...")
        data = get_action_runs()
        runs = data.get("workflow_runs", [])
        if not runs:
            ui_warn("目前尚無執行紀錄或 API 未返回 runs。")
            return
        ui_header(f"Gitea Actions 最近執行結果 (共 {len(runs)} 筆)")
        for r in runs[:10]:
            run_id = r.get("id")
            title = r.get("title", "Unknown")
            status = r.get("status", "unknown")
            conclusion = r.get("conclusion", "")
            disp_status = conclusion if (status == "completed" and conclusion) else status
            event = r.get("event", "")
            created = r.get("created_at", "")[:19].replace("T", " ")
            symbol = "✅" if disp_status == "success" else ("⏳" if disp_status in ("running", "waiting") else "❌")
            print(f"  {symbol} #{run_id:<4} [{disp_status.upper():<7}] {title:<35} (Event: {event}, {created})")
        print()
        try:
            inspect_id = input("🔍 請輸入欲查看錯誤診斷與日誌反饋的 Run ID (按 Enter 返回): ").strip()
            if inspect_id and inspect_id.isdigit():
                display_run_error_feedback(int(inspect_id))
        except (KeyboardInterrupt, EOFError):
            pass

    def _act_self_update():
        from sync_ops_tools import update_tools_from_gitea
        update_tools_from_gitea()

    tui.add_category(
        t("tools.cat_maintenance", "🛠️ 系統維護自檢"),
        t("tools.cat_maintenance_desc", "全網連通性探測、CI/CD 執行診斷與工具鏈更新"),
        [
            {"name": t("tools.act_conn_local", "全網節點 SSH/TCP 即時連通性探測"), "desc": t("tools.act_conn_local_desc", "在當前控制台直接並行測試全節點 TCP 端口與免密 SSH"), "action": _act_connectivity_local},
            {"name": t("tools.act_conn_gitea", "Gitea Actions 雲端連通性檢測"), "desc": t("tools.act_conn_gitea_desc", "派發 SSH 與各項服務連通性檢測至 Gitea Actions 矩陣"), "action": _act_connectivity_gitea},
            {"name": t("tools.act_inspect_runs", "Gitea Actions 執行紀錄檢視"), "desc": t("tools.act_inspect_runs_desc", "查詢近期自動化 Workflow 執行紀錄與錯誤診斷日誌"), "action": _act_inspect_runs},
            {"name": t("tools.act_self_update", "sync-ops-tools 自我更新"), "desc": t("tools.act_self_update_desc", "自 Gitea 伺服器同步並升級本地維運工具鏈"), "action": _act_self_update},
            {"name": t("tools.act_linear_menu", "切換至傳統序列式文字選單"), "desc": t("tools.act_linear_menu_desc", "離開 Curses TUI，切換至傳統逐行數字選擇選單"), "action": linear_interactive_menu},
        ]
    )

    run_tui(tui)


def linear_interactive_menu():
    """傳統序列式純文字選單 (保留給非人類、腳本、自動化或不支援 curses 的環境)。"""
    from core.version import get_local_version
    local_ver = get_local_version()

    title = t("tools.menu_title", f"OpenLabOps Cluster Management Console (lab-tools v{local_ver})")
    ui_header(f"{title} [v{local_ver}]")
    ui_kv(t("common.current_host", "目前主機"), socket.gethostname())
    ui_kv(t("common.os", "作業系統"), f"{platform.system()} {platform.release()}")
    ui_kv(t("common.locale", "當前語系"), get_locale())
    ui_divider()

    options = [
        t("tools.opt_setup", "🚀 [Setup] 伺服器初建與全網 IaC 基線更新 (lab-setup)"),
        t("tools.opt_ssh", "🔑 [SSH] 叢集金鑰管理與輪換控制台 (lab-ssh)"),
        t("tools.opt_node", "🖥️ [Node] 節點動態納管與引導精靈 (lab-node add / list)"),
        t("tools.opt_info", "📝 [Info] 全網節點手冊採集、工作區同步與渲染 (lab-info)"),
        t("tools.opt_backup", "💾 [Backup] 叢集組態備份與共用組態廣播 (lab-backup)"),
        t("tools.opt_upgrade", "📦 [Upgrade] 叢集套件維護升級與重開機提醒 (lab-upgrade)"),
        t("tools.opt_iac", "📋 [IaC] 全網節點套件清冊比對與同步 (sync-package-inventory)"),
        t("tools.opt_config", "⚙️ [Config] 宣告式組態比對與推播 (lab-config)"),
        t("tools.opt_probe", "🌐 [Network] 全網節點 SSH 與服務連通性檢測 (test-connectivity)"),
        t("tools.opt_runs", "📊 [Actions] 查看 Gitea Actions 執行紀錄與錯誤診斷 (inspect-run)"),
        t("tools.opt_sync_tools", "⚡ [Tools] 檢查並更新維運工具鏈 (sync-ops-tools)"),
        t("tools.opt_exit", "❌ 退出控制台")
    ]

    try:
        choice_idx, selected_val = ui_select(t("tools.menu_prompt", "請選取要執行的自動化套件任務:"), options)
    except (EOFError, KeyboardInterrupt):
        print()
        ui_info(t("tools.exit_msg", "已退出 lab-tools 控制台。"))
        return

    if choice_idx == 1:
        s_idx, s_val = ui_select(t("tools.setup_mode_title", "【lab-setup 伺服器初建與基線更新】請選取模式:"), [
            t("tools.setup_mode_opt1", "🚀 [預設一鍵] 執行全網伺服器節點基線設定與容器環境掛載 (system-base-setup.yml)"),
            t("tools.setup_mode_opt2", "🛠️ 進入 lab-setup 獨立控制台 (細部步驟微調與手動觸發)")
        ])
        if s_idx == 1:
            target_hosts = input(t("tools.setup_target_prompt", "請輸入目標伺服器群組 (預設: servers): ")).strip() or "servers"
            if ui_confirm(t("tools.setup_confirm", f"確定要對 [{target_hosts}] 執行全域基線更新與全節點 IaC 套用？", hosts=target_hosts), "y"):
                from lab_setup import run_full_system_setup
                run_full_system_setup(target_hosts)
        elif s_idx == 2:
            from lab_setup import ServerSetupRegistry, interactive_menu as setup_menu
            setup_menu(ServerSetupRegistry())

    elif choice_idx == 2:
        s_idx, s_val = ui_select(t("tools.ssh_mode_title", "【lab-ssh 金鑰管理與輪換】請選取模式:"), [
            t("tools.ssh_mode_opt1", "🚀 [預設一鍵] 依序輪換全網所有伺服器 SSH 金鑰 (Lab ➔ OpenLabOps ➔ Git)"),
            t("tools.ssh_mode_opt2", "🔑 進入 lab-ssh 獨立控制台 (單項金鑰輪換、端點金鑰生成/撤銷、金鑰同步)")
        ])
        if s_idx == 1:
            if ui_confirm(t("tools.ssh_confirm", "確定要依序輪換全網伺服器金鑰並同步至 dev 群組？"), "y"):
                from lab_ssh import rotate_all_server_keys
                rotate_all_server_keys(target_nodes="dev")
        elif s_idx == 2:
            from lab_ssh import interactive_menu as ssh_menu
            ssh_menu()

    elif choice_idx == 3:
        from lab_node import interactive_menu as node_menu
        node_menu()

    elif choice_idx == 4:
        i_idx, i_val = ui_select(t("tools.info_mode_title", "【lab-info 節點資訊與工作區同步】請選取模式:"), [
            t("tools.info_mode_opt1", "🚀 [預設一鍵] 遠端全網巡檢 ➔ 本機工作區 Pull 同步 ➔ 渲染 Markdown 手冊"),
            t("tools.info_mode_opt2", "📝 進入 lab-info 獨立控制台 (單項遠端巡檢、工作區 Pull、Markdown 轉出)")
        ])
        if i_idx == 1:
            if ui_confirm(t("tools.info_confirm", "確定要執行完整的節點手冊巡檢、工作區同步與 Obsidian 手冊渲染？"), "y"):
                from lab_info import run_full_sync_cycle
                run_full_sync_cycle()
        elif i_idx == 2:
            from lab_info import interactive_menu as info_menu
            info_menu()

    elif choice_idx == 5:
        b_idx, b_val = ui_select(t("tools.backup_mode_title", "【lab-backup 叢集備份與組態廣播】請選取模式:"), [
            t("tools.backup_mode_opt1", "🚀 [預設一鍵] 依序執行閘道備份與本機共用組態廣播 (Family Deploy)"),
            t("tools.backup_mode_opt2", "💾 進入 lab-backup 獨立控制台 (單項備份、共用組態採集廣播)")
        ])
        if b_idx == 1:
            current_host = socket.gethostname().split('.')[0].lower()
            if ui_confirm(t("tools.backup_confirm", "確定要依序執行網關備份與共用組態全網廣播？"), "y"):
                from lab_backup import run_full_backup_suite
                run_full_backup_suite(current_host)
        elif b_idx == 2:
            from lab_backup import interactive_menu as backup_menu
            backup_menu()

    elif choice_idx == 6:
        from lab_upgrade import upgrade_cluster
        upgrade_cluster()

    elif choice_idx == 7:
        m_idx, m_val = ui_select("請選擇 IaC 比對/同步模式:", [
            "🔍 純比對漂移報告 (Audit Only - 僅產出報告，不變更 host_vars)",
            "✍️ 比對並更新至 host_vars (Apply Sync - 同步主機現狀至 IaC)"
        ])
        if m_idx == 1:
            if ui_confirm("確定要在 Gitea Actions 上執行純漂移檢查 (Audit Only)？", "y"):
                trigger_sync_packages(apply_sync=False)
        elif m_idx == 2:
            if ui_confirm("確定要在 Gitea Actions 上執行同步並寫入 host_vars (Apply Sync)？", "y"):
                trigger_sync_packages(apply_sync=True)

    elif choice_idx == 8:
        from lab_config import main as config_main
        config_main([])

    elif choice_idx == 9:
        c_idx, c_val = ui_select("【全網節點與服務連通性檢測】請選取模式:", [
            "🚀 [預設本地] 當前本機直接並行探測全網節點 TCP 端口與 SSH 免密狀態",
            "🌐 透過 Gitea Actions 雲端/集群派發檢測 (test-connectivity.yml)"
        ])
        if c_idx == 1:
            run_local_connectivity_test()
        elif c_idx == 2:
            trigger_connectivity_test()

    elif choice_idx == 10:
        from core.gitea_api import get_action_runs, display_run_error_feedback
        ui_info("正在查詢 Gitea Actions 最近執行紀錄...")
        data = get_action_runs()
        runs = data.get("workflow_runs", [])
        if not runs:
            ui_warn("目前尚無執行紀錄或 API 未返回 runs。")
        else:
            ui_header(f"Gitea Actions 最近執行結果 (共 {len(runs)} 筆)")
            for r in runs[:10]:
                run_id = r.get("id")
                title = r.get("title", "Unknown")
                status = r.get("status", "unknown")
                conclusion = r.get("conclusion", "")
                disp_status = conclusion if (status == "completed" and conclusion) else status
                event = r.get("event", "")
                created = r.get("created_at", "")[:19].replace("T", " ")
                symbol = "✅" if disp_status == "success" else ("⏳" if disp_status in ("running", "waiting") else "❌")
                print(f"  {symbol} #{run_id:<4} [{disp_status.upper():<7}] {title:<35} (Event: {event}, {created})")

            print()
            try:
                inspect_id = input("🔍 請輸入欲查看錯誤診斷與日誌反饋的 Run ID (按 Enter 返回): ").strip()
                if inspect_id and inspect_id.isdigit():
                    display_run_error_feedback(int(inspect_id))
            except (KeyboardInterrupt, EOFError):
                pass

    elif choice_idx == 11:
        from sync_ops_tools import update_tools_from_gitea
        update_tools_from_gitea()

    elif choice_idx == 12:
        ui_info("已退出 lab-tools 控制台。")
        sys.exit(0)



if __name__ == "__main__":
    main()
