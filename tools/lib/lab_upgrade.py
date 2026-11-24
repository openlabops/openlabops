#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Cluster Package Upgrade & Maintenance Suite (lab-upgrade)
負責跨發行版全網伺服器套件升級維護與重開機需求識別。
核心原則：
1. 依作業系統原生套件管理器 (pacman, tdnf, dnf, pkg) 執行安全升級
2. 預設採用【多節點並行同步升級 (Live Dashboard)】，極速完成全網維護
3. 升級後即時探測核心 (Kernel) 與關鍵函式庫是否發生變更
4. 升級完畢後主動提醒哪些機器需要 reboot，絕不擅自直接重開機 (純手工運維安全至上)
5. 升級若遇異常【自動提取關鍵錯誤日誌並彙整】，無需管理者手動翻找 log
"""

import os
import re
import sys
import time
import shlex
import shutil
import atexit
import tempfile
import argparse
import subprocess
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error, C_BOLD, C_RESET, C_CYAN, C_GREEN, C_YELLOW, C_RED, C_DIM
from core.ui_menu import ui_confirm, ui_select
from core.config import get_path, get_ansible_user, is_openlab, TOOLS_ROOT
from core.live_probe import CLUSTER_TARGETS, probe_all_cluster_nodes, probe_single_node

ANSIBLE_KEY = get_path("ssh_dir", os.path.expanduser("~/.ssh")) + "/ansible.key"
USER_KEY = get_path("ssh_dir", os.path.expanduser("~/.ssh")) + "/id_user.key"
_UPGRADE_LOG_DIR = tempfile.mkdtemp(prefix="lab-upgrade-")
atexit.register(lambda: shutil.rmtree(_UPGRADE_LOG_DIR, ignore_errors=True))

ANSI_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi(s: str) -> str:
    """去除字串中之 ANSI 跳脫色彩字元"""
    return ANSI_PATTERN.sub('', s)


def pad_visible(s: str, width: int) -> str:
    """依可見字元長度對齊，避免 ANSI 顏色控制碼導致表格錯位"""
    vis_len = len(strip_ansi(s))
    pad = max(0, width - vis_len)
    return s + (" " * pad)


def extract_stage_summary(line: str) -> str:
    """從套件管理器輸出中提取精簡進度標籤 (最多 36 字元)"""
    clean = strip_ansi(line).strip()
    if not clean:
        return ""

    # DNF / TDNF / Yum 模式
    if "Downloading Packages" in clean:
        return "下載套件包中..."
    if "Running transaction" in clean or "Verifying" in clean:
        return "執行交易與套件驗證中..."
    if "Complete!" in clean or "done!" in clean:
        return "套件安裝與交易完成"

    for prefix in ("Upgrading:", "Installing:", "Upgrading", "Installing"):
        if clean.startswith(prefix):
            parts = clean[len(prefix):].strip().split()
            if parts:
                return f"安裝: {parts[0][:26]}"
            return f"處理: {prefix.rstrip(':')}"

    # Arch pacman / yay 模式
    if "downloading" in clean.lower():
        parts = clean.split()
        if parts:
            return f"下載: {parts[-1][:26]}"
    if "upgrading" in clean.lower() or "installing" in clean.lower():
        parts = clean.split()
        if parts:
            return f"安裝: {parts[-1][:26]}"

    if len(clean) <= 36:
        return clean
    return clean[:33] + "..."


def get_upgrade_command(target: dict) -> tuple:
    """依 Distro 產生原生升級指令與連線身分"""
    hname = target["name"]
    host_addr = target.get("host", hname)
    mgr = target.get("mgr", "pkg")
    target_user = target.get("target_user") or target.get("user") or get_ansible_user()
    ssh_dest = shlex.quote(f"{target_user}@{host_addr}")
    ssh_key = shlex.quote(ANSIBLE_KEY)

    if target.get("is_local"):
        # Local system package manager
        if shutil.which("yay"):
            return "yay -Syu --noconfirm --needed", "local"
        if shutil.which("pacman"):
            return "sudo pacman -Syu --noconfirm", "local"
        if shutil.which("apt-get"):
            return "sudo apt-get update && sudo apt-get dist-upgrade -y", "local"
        if shutil.which("dnf"):
            return "sudo dnf upgrade -y", "local"
        return "yay -Syu --noconfirm --needed", "local"

    if mgr in ("dnf", "yum"):
        cmd = f"ssh -o BatchMode=yes -i {ssh_key} {ssh_dest} 'sudo dnf upgrade -y'"
        return cmd, "remote_dnf"

    if mgr == "apt":
        cmd = f"ssh -o BatchMode=yes -i {ssh_key} {ssh_dest} 'sudo apt-get update && sudo apt-get dist-upgrade -y'"
        return cmd, "remote_apt"

    if mgr == "pacman":
        cmd = f"ssh -o BatchMode=yes -i {ssh_key} {ssh_dest} 'sudo pacman -Syu --noconfirm'"
        return cmd, "remote_pacman"

    if mgr == "apk":
        cmd = f"ssh -o BatchMode=yes -i {ssh_key} {ssh_dest} 'sudo apk update && sudo apk upgrade'"
        return cmd, "remote_apk"

    if mgr == "tdnf":
        # Photon OS Core Servers
        cmd = f"ssh -o BatchMode=yes -i {ssh_key} {ssh_dest} 'sudo tdnf update -y'"
        return cmd, "remote_photon"

    return "", f"不支援自動升級或嵌入式系統: {hname}"


class NodeUpgradeState:
    """節點升級狀態追蹤物件 (支援多執行緒並行看板與錯誤提取)"""
    def __init__(self, target: dict):
        self.target = target
        self.hostname = target["name"]
        self.status = "queued"  # queued, running, probing, success, failed
        self.stage = "等待排程..."
        self.start_time = None
        self.end_time = None
        self.elapsed = 0.0
        self.success = False
        self.err_msg = ""
        self.needs_reboot = False
        self.reboot_reason = ""
        self.bsd_two_stage = False
        self.recent_lines = deque(maxlen=30)
        self.error_lines = []
        self.log_file = os.path.join(_UPGRADE_LOG_DIR, f"lab-upgrade-{self.hostname}.log")


def worker_upgrade_node(state: NodeUpgradeState):
    """單一節點升級工作執行緒"""
    target = state.target
    hname = state.hostname
    cmd, mode = get_upgrade_command(target)

    if not cmd:
        state.status = "failed"
        state.err_msg = mode
        state.stage = mode
        return

    state.status = "running"
    state.start_time = time.time()
    state.stage = "連線啟動中..."

    try:
        with open(state.log_file, "w", encoding="utf-8") as log_f:
            log_f.write(f"=== lab-Upgrade Log: {hname} ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
            log_f.write(f"Command: {cmd}\n\n")
            log_f.flush()

            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for raw_line in proc.stdout:
                log_f.write(raw_line)
                log_f.flush()
                clean = raw_line.strip()
                if not clean:
                    continue

                state.recent_lines.append(clean)

                if "again to finish installing updates" in clean or "Kernel updates have been installed" in clean:
                    state.bsd_two_stage = True

                clean_lower = clean.lower()
                if any(kw in clean_lower for kw in ["error:", "failed", "fatal:", "conflict", "denied", "cannot open", "not found", "transaction check error"]):
                    state.error_lines.append(clean)

                try:
                    summary = extract_stage_summary(clean)
                    if summary:
                        state.stage = summary
                except Exception:
                    pass

            proc.wait()
            state.end_time = time.time()
            state.elapsed = state.end_time - state.start_time

            if proc.returncode == 0:
                state.status = "probing"
                state.stage = "探測核心重開狀態..."
                try:
                    post_probe = probe_single_node(target)
                    state.needs_reboot = post_probe.get("reboot_required", False)
                    state.reboot_reason = post_probe.get("reboot_reason", "")
                except Exception as e:
                    state.needs_reboot = False
                    state.reboot_reason = f"探測異常: {e}"

                state.success = True
                state.status = "success"
                rb_tag = f" (🔄 需重開: {state.reboot_reason})" if state.needs_reboot else " (● 無需重開)"
                state.stage = f"升級完成{rb_tag}"
            else:
                state.status = "failed"
                state.success = False
                state.err_msg = f"指令結束代碼: {proc.returncode}"
                state.stage = f"升級異常 (Exit {proc.returncode})"

    except Exception as e:
        state.status = "failed"
        state.success = False
        state.err_msg = str(e)
        state.stage = f"執行異常: {str(e)[:25]}"
        state.elapsed = time.time() - (state.start_time or time.time())


def run_parallel_upgrades(candidates: list) -> list:
    """多節點並行同步升級引擎 (動態原地儀表板)"""
    states = [NodeUpgradeState(c) for c in candidates]
    max_workers = min(len(candidates), 8)

    spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame_idx = 0
    is_tty = sys.stdout.isatty()
    last_rendered_lines_count = 0

    def build_dashboard_lines(spin_char: str) -> list:
        dash_lines = []
        dash_lines.append(f"{C_CYAN}╭── 🚀 叢集節點同步升級看板 (Parallel Upgrade Dashboard) ──────────────────╮{C_RESET}")
        header_text = f"  {pad_visible('節點主機', 10)} {pad_visible('狀態', 10)} {pad_visible('耗時', 7)} {pad_visible('當前進度與階段摘要', 38)}"
        dash_lines.append(f"{C_CYAN}│{C_RESET}{C_BOLD}{header_text}{C_RESET} {C_CYAN}│{C_RESET}")
        dash_lines.append(f"{C_CYAN}│{C_RESET} {C_DIM}{'─' * 70}{C_RESET} {C_CYAN}│{C_RESET}")

        for s in states:
            h = s.hostname
            el = (time.time() - s.start_time) if s.start_time else 0.0
            if s.end_time:
                el = s.elapsed
            el_str = f"{int(el//60):02d}:{int(el%60):02d}"

            if s.status == "queued":
                st_str = f"{C_DIM}⏳ 排隊中{C_RESET}"
            elif s.status == "running":
                st_str = f"{C_YELLOW}{spin_char} 升級中{C_RESET}"
            elif s.status == "probing":
                st_str = f"{C_CYAN}{spin_char} 探測中{C_RESET}"
            elif s.status == "success":
                st_str = f"{C_GREEN}● 成功{C_RESET}  "
            else:
                st_str = f"{C_RED}✖ 失敗{C_RESET}  "

            st_padded = pad_visible(st_str, 10)
            h_padded = pad_visible(h, 10)
            el_padded = pad_visible(el_str, 7)
            stage_padded = pad_visible(s.stage[:38], 38)

            row = f"  {h_padded} {st_padded} {el_padded} {stage_padded}"
            dash_lines.append(f"{C_CYAN}│{C_RESET}{row} {C_CYAN}│{C_RESET}")

        dash_lines.append(f"{C_CYAN}╰────────────────────────────────────────────────────────────────────────────╯{C_RESET}")
        return dash_lines

    print(f"\n{C_BOLD}已為 {len(candidates)} 台節點發起並行同步升級 (即時日誌留存於 /tmp/lab-upgrade-<host>.log):{C_RESET}\n")

    initial_lines = build_dashboard_lines(spinners[0])
    if is_tty:
        for l in initial_lines:
            sys.stdout.write(l + "\n")
        sys.stdout.flush()
        last_rendered_lines_count = len(initial_lines)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker_upgrade_node, s): s for s in states}

        while any(not f.done() for f in futures):
            time.sleep(0.12)
            frame_idx += 1
            spin_char = spinners[frame_idx % len(spinners)]

            if is_tty:
                dash_lines = build_dashboard_lines(spin_char)
                sys.stdout.write(f"\033[{last_rendered_lines_count}A")
                for l in dash_lines:
                    sys.stdout.write(f"\033[2K\r{l}\n")
                sys.stdout.flush()
                last_rendered_lines_count = len(dash_lines)

    # 最終靜態幀渲染
    if is_tty:
        final_lines = build_dashboard_lines("✔")
        sys.stdout.write(f"\033[{last_rendered_lines_count}A")
        for l in final_lines:
            sys.stdout.write(f"\033[2K\r{l}\n")
        sys.stdout.flush()
    else:
        for l in build_dashboard_lines("✔"):
            print(l)

    return states


def run_serial_upgrades(candidates: list) -> list:
    """單台循序升級模式 (供除錯或傳統逐台串流日誌需求)"""
    states = []
    for c in candidates:
        s = NodeUpgradeState(c)
        states.append(s)
        hname = s.hostname
        cmd, mode = get_upgrade_command(c)
        ui_info(f"🚀 開始對節點 [{hname}] 執行原生套件升級 ({mode})...")
        ui_kv("執行指令", cmd)

        s.status = "running"
        s.start_time = time.time()
        try:
            with open(s.log_file, "w", encoding="utf-8") as log_f:
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in proc.stdout:
                    log_f.write(line)
                    log_f.flush()
                    clean = line.strip()
                    if clean:
                        s.recent_lines.append(clean)
                        if any(kw in clean.lower() for kw in ["error:", "failed", "fatal:", "conflict"]):
                            s.error_lines.append(clean)
                        if any(kw in clean for kw in ["Upgrading", "Installing", "Complete", "done", "Processing", "affected", "Total", "Resolving", "Running transaction"]):
                            print(f"  \033[2m[{hname}]\033[0m {clean[:80]}")
                proc.wait()
                s.elapsed = time.time() - s.start_time
                if proc.returncode == 0:
                    s.status = "success"
                    s.success = True
                    ui_success(f"節點 [{hname}] 套件升級成功 (耗時 {s.elapsed:.1f}s)！正在進行重開機需求探測...")
                    post_probe = probe_single_node(c)
                    s.needs_reboot = post_probe.get("reboot_required", False)
                    s.reboot_reason = post_probe.get("reboot_reason", "")
                else:
                    s.status = "failed"
                    s.success = False
                    s.err_msg = f"指令回傳錯誤代碼: {proc.returncode}"
                    ui_warn(f"節點 [{hname}] 套件升級異常: {s.err_msg}")
        except Exception as e:
            s.status = "failed"
            s.success = False
            s.err_msg = str(e)
            s.elapsed = time.time() - s.start_time
            ui_warn(f"節點 [{hname}] 執行失敗: {e}")

        ui_divider()

    return states


def upgrade_cluster(target_hosts: list = None, force: bool = False, serial: bool = False):
    """全網或指定伺服器節點套件升級維護工作流"""
    ui_header("OpenLabOps Cluster Package Upgrade (lab-upgrade)")

    # 1. 先探測節點更新現況
    ui_info("正在並行探測全網各節點之待升級套件現況...")
    res_map, probe_elapsed = probe_all_cluster_nodes()
    ui_success(f"探測完成 (全網活體耗時 {probe_elapsed:.2f}s)。")

    # 2. 確定升級目標清單
    candidates = []
    if target_hosts:
        for th in target_hosts:
            t = next((node for node in CLUSTER_TARGETS if node["name"] == th), None)
            if t:
                candidates.append(t)
            else:
                ui_warn(f"找不到指定節點: {th}")
    else:
        for node in CLUSTER_TARGETS:
            hname = node["name"]
            info = res_map.get(hname, {})
            if info.get("upg_count", 0) > 0:
                candidates.append(node)

    if not candidates:
        ui_success("🎉 全網所有受控節點目前皆已是最新版本，無任何待升級套件！")
        return

    if not target_hosts and not force:
        from core.ui_menu import ui_checklist
        chk_options = [
            f"{c['name']:10} : ▲ {res_map.get(c['name'], {}).get('upg_count', 0)} 待更新 ({', '.join(res_map.get(c['name'], {}).get('upg_samples', []))})"
            for c in candidates
        ]
        selected_indices = ui_checklist(
            "請勾選欲執行套件升級之目標伺服器 (空白鍵切換 [X]):",
            chk_options,
            checked_indices=list(range(1, len(candidates) + 1))
        )
        if not selected_indices:
            ui_info("未選取任何節點，取消升級作業。")
            return
        candidates = [candidates[i - 1] for i in selected_indices]

    mode_name = "循序單台串流模式" if serial else "多節點同步並行模式 (Live Dashboard)"
    print(f"\n{C_BOLD}待維護升級之目標節點清單 ({C_CYAN}{mode_name}{C_RESET}{C_BOLD}):{C_RESET}")
    for c in candidates:
        d = res_map.get(c["name"], {})
        samples = ", ".join(d.get("upg_samples", []))
        print(f"  • {C_CYAN}{c['name']:10}{C_RESET} : {C_YELLOW}▲ {d.get('upg_count', 0)} 待更新{C_RESET} ({samples})")

    if not force:
        action_verb = "循序執行" if serial else "同時同步並行"
        try:
            confirm = input(f"\n確定要對上述 {len(candidates)} 台節點{action_verb}升級作業？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = "no"
            print()
        if confirm not in ("y", "yes"):
            ui_info("使用者取消升級作業。")
            return

    ui_divider()

    # 3. 執行升級 (預設並行看板，亦可選循序)
    t_start = time.time()
    if serial:
        states = run_serial_upgrades(candidates)
    else:
        states = run_parallel_upgrades(candidates)
    total_elapsed = time.time() - t_start

    # 4. 結算報表與核心 Reboot 醒目標示
    print(f"\n{C_BOLD}{C_CYAN}============================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  📊 OpenLabOps 叢集套件升級維護作業結算報表{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}============================================================{C_RESET}")

    reboot_needed_hosts = []
    failed_states = []

    for s in states:
        h = s.hostname
        st = f"{C_GREEN}● 升級成功{C_RESET}" if s.success else f"{C_RED}✖ 失敗 ({s.err_msg}){C_RESET}"
        if s.needs_reboot:
            reboot_needed_hosts.append(h)
            rb_str = f"{C_RED}🔄 需要重開機{C_RESET} ({s.reboot_reason})"
        else:
            rb_str = f"{C_GREEN}● 無需重開機{C_RESET}"

        if not s.success:
            failed_states.append(s)

        print(f"  • {h:12} : 狀態={st:20} 重開狀態={rb_str:25} (耗時: {s.elapsed:.1f}s)")

    print(f"{C_BOLD}{C_CYAN}────────────────────────────────────────────────────────────{C_RESET}")
    print(f"總作業耗時: {C_BOLD}{total_elapsed:.1f}s{C_RESET} | 成功: {C_GREEN}{len(candidates)-len(failed_states)}{C_RESET} / 失敗: {C_RED}{len(failed_states)}{C_RESET}")

    # 5. 核心需求：錯誤自動彙整專區 (Error Log Aggregation)
    # 絕不讓使用者翻找 log，自動自日誌中提取最後/關鍵錯誤行
    if failed_states:
        print(f"\n{C_BOLD}{C_RED}============================================================{C_RESET}")
        print(f"{C_BOLD}{C_RED}  🚨 升級異常節點錯誤日誌彙整 (已為您自日誌自動提取關鍵錯誤)  {C_RESET}")
        print(f"{C_BOLD}{C_RED}============================================================{C_RESET}")
        for fs in failed_states:
            h = fs.hostname
            print(f"\n{C_BOLD}{C_YELLOW}╭── ❌ 節點: {h} ({fs.err_msg}) ───────────────────────────────────────╮{C_RESET}")
            print(f"│ {C_DIM}日誌檔案: {fs.log_file}{C_RESET}")
            print(f"│ {C_BOLD}關鍵錯誤日誌摘要:{C_RESET}")
            print(f"│ {C_DIM}────────────────────────────────────────────────────────────────────{C_RESET}")

            display_lines = []
            if fs.error_lines:
                seen = set()
                for el in fs.error_lines[-12:]:
                    if el not in seen:
                        display_lines.append(el)
                        seen.add(el)
            if not display_lines:
                display_lines = list(fs.recent_lines)[-12:]

            if not display_lines:
                display_lines = ["(無錯誤輸出，請檢查網路連線或 sudo 提權設定)"]

            for dl in display_lines:
                clean_dl = strip_ansi(dl).strip()
                print(f"│   {C_RED}> {clean_dl[:74]}{C_RESET}")

            print(f"{C_BOLD}{C_YELLOW}╰────────────────────────────────────────────────────────────────────╯{C_RESET}")

    # 6. 遵照規範：純手工維護，明確提醒重開機，絕不擅自重開
    if reboot_needed_hosts:
        print(f"\n{C_BOLD}{C_YELLOW}📢 【重要重開機提醒 (Reboot Reminder)】{C_RESET}")
        print(f"{C_YELLOW}本工具遵循高可用運維規範【絕不擅自執行重開機】。{C_RESET}")
        print(f"檢測到下列節點核心或關鍵系統函式庫已完成升級，{C_BOLD}{C_RED}必須進行重開機{C_RESET}以載入新版本：")
        for h in reboot_needed_hosts:
            print(f"  👉 {C_BOLD}{C_RED}{h}{C_RESET}")
        print(f"\n{C_CYAN}手動重開機指引:{C_RESET}")
        print(f"  請管理者依據各業務容器與網路服務之維護窗口，手動登入節點執行重啟:")
        for h in reboot_needed_hosts:
            print(f"  • ssh {h} 'sudo reboot'")
        print()
    elif not failed_states:
        print(f"\n{C_GREEN}🎉 全數升級完成！所有節點均無需重開機，系統運作正常。{C_RESET}")

    # 7. 檢查並同步維運工具鏈版本 (本機 + 遠端受管節點)
    try:
        import sync_ops_tools
        local_ver = sync_ops_tools.get_local_version()
        remote_ver = sync_ops_tools.get_remote_version()
        if remote_ver and sync_ops_tools._parse_semver(remote_ver) > sync_ops_tools._parse_semver(local_ver):
            ui_info(f"發現新版維運工具鏈 v{remote_ver} (本機目前: v{local_ver})，準備同步升級...")
            if force or ui_confirm(f"是否同步更新本機與目標節點之維運工具鏈至 v{remote_ver}？", default="y"):
                sync_ops_tools.update_tools_from_gitea(force=True, check_only=False)
                from core.gitea_api import gitea_dispatch
                dispatch_target = ",".join(target_hosts) if target_hosts else "all"
                gitea_dispatch("deploy-ops-tools.yml", {"ref": "main", "inputs": {"target_hosts": dispatch_target}})
    except Exception:
        pass


def main():
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="lab-upgrade", description=t("upgrade.cli_desc", "OpenLabOps Cluster Package Upgrade (lab-upgrade)"))
    parser.add_argument("hosts", nargs="*", help=t("upgrade.cli_hosts", "Target nodes to upgrade (default: auto-select nodes with pending updates)"))
    parser.add_argument("-s", "--serial", action="store_true", help=t("upgrade.cli_serial", "Run serial single-node upgrade with streaming logs (default: parallel dashboard)"))
    parser.add_argument("-f", "--force", action="store_true", help=t("upgrade.cli_force", "Start upgrade without confirmation"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))

    args = parser.parse_args()

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Cluster Package Upgrade (lab-upgrade)")
        return

    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard("lab-upgrade")

    targets = [h.strip().lower() for h in args.hosts if h.strip()]
    upgrade_cluster(target_hosts=targets, force=args.force, serial=args.serial)


if __name__ == "__main__":
    main()
