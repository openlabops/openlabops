#!/usr/bin/env python3
"""
OpenLabOps Server Setup & Integration Trigger Suite (Extensible Console)
負責統籌伺服器初次建置、Git Hook 部署、Docker Compose 同步與金鑰發放等自動化 Trigger 集成。
"""

import os
import sys
import shutil
import argparse
import socket
import platform
import subprocess
from pathlib import Path
from typing import List, Callable, Dict, Optional

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, C_CYAN, C_BOLD, C_RESET, C_DIM
from core.ui_menu import ui_select, ui_confirm
from core.config import get_cluster_prefix
from core.version import get_local_version
from core.gitea_api import gitea_dispatch, load_gitea_token
from core.lockout import enforce_lockout_guard


class SetupStep:
    """伺服器建置 Trigger 步驟定義物件"""
    def __init__(
        self,
        step_id: str,
        name: str,
        description: str,
        workflow_file: str,
        playbook_path: str,
        enabled: bool = True,
        handler: Optional[Callable] = None
    ):
        self.step_id = step_id
        self.name = name
        self.description = description
        self.workflow_file = workflow_file
        self.playbook_path = playbook_path
        self.enabled = enabled
        self.handler = handler

    def run(self, mode: str = "gitea") -> bool:
        ui_info(f"👉 執行任務 [{self.step_id}]: {self.name}")
        ui_kv("說明", self.description)

        if self.handler is not None and (mode == "local" or not self.workflow_file):
            ui_kv("模式", "Python 本地整合執行")
            return bool(self.handler())

        ui_kv("模式", "Gitea CI Dispatch" if mode == "gitea" else "Ansible Local Execution")

        if mode == "gitea":
            if not self.workflow_file:
                if self.handler:
                    return bool(self.handler())
                ui_warn(f"步驟 [{self.step_id}] 無遠端工作流對應。")
                return False
            return gitea_dispatch(self.workflow_file, {"ref": "main"})
        else:
            enforce_lockout_guard()
            ansible_bin = shutil.which("ansible-playbook")
            pb_tokens = self.playbook_path.split() if self.playbook_path else []
            play_file = pb_tokens[0] if pb_tokens else ""
            extra_pb_args = pb_tokens[1:] if len(pb_tokens) > 1 else []
            candidate_roots = [
                Path(__file__).resolve().parent.parent.parent / "ansible",
                Path.home() / "openlab-ansible",
                Path.home() / "openlabops" / "ansible",
            ]
            ansible_root = next((p for p in candidate_roots if (p / "inventory" / "hosts.yml").exists()), candidate_roots[0])
            inv_path = ansible_root / "inventory" / "hosts.yml"
            play_target = ansible_root / play_file
            if play_file and not play_target.exists():
                ext_candidate = ansible_root.parent / "extensions" / play_file
                if ext_candidate.exists():
                    play_target = ext_candidate

            if self.handler and (not ansible_bin or not play_target.exists()):
                return bool(self.handler())
            cmd_list = ["ansible-playbook", "-i", str(inv_path), str(play_target)] + extra_pb_args
            ui_info(f"執行指令: {' '.join(cmd_list)}")
            res = subprocess.run(cmd_list)
            if res.returncode == 0:
                ui_success(f"任務 [{self.step_id}] 執行成功！")
                return True
            else:
                ui_warn(f"任務 [{self.step_id}] 執行失敗，回傳碼: {res.returncode}")
                return False


class ServerSetupRegistry:
    """可擴充 Setup 步驟註冊管理器"""
    def __init__(self):
        self.steps: Dict[str, SetupStep] = {}
        self._register_default_steps()

    def register(self, step: SetupStep):
        """註冊新的 Server Setup Trigger 步驟"""
        self.steps[step.step_id] = step

    def _register_default_steps(self):
        """預設整合之 Trigger 步驟"""
        # Step 0: Sync SSH Client Configuration (~/.ssh/config)
        from sync_ssh_config import sync_ssh_config
        self.register(SetupStep(
            step_id="sync_ssh_config",
            name="0. 同步本機標準 ~/.ssh/config 連線別名設定",
            description="從 Gitea REST API 獲取標準 SSH 別名與設定，確保連線參數全網一致",
            workflow_file="",
            playbook_path="playbooks/deploy-dotfiles.yml --tags ssh_config",
            handler=lambda: sync_ssh_config()
        ))

        # Step 0.1: Sync Managed SSH Keys (~/.ssh/*.key)
        from sync_ssh_keys import sync_ssh_keys
        self.register(SetupStep(
            step_id="sync_ssh_keys",
            name="0.1 同步本機受控 SSH 管理金鑰 (~/.ssh/*.key)",
            description="從 Gitea REST API (openlab-secrets) 獲取最新管理金鑰與公鑰 (openlab, kvm, lab)",
            workflow_file="",
            playbook_path="",
            handler=lambda: sync_ssh_keys()
        ))

        # Step 0.2: Deploy Ops Tools via Runner Playbook
        self.register(SetupStep(
            step_id="deploy_ops_tools",
            name="0.2 派發節點維運工具鏈安裝與更新 (/usr/local/bin/openlab)",
            description="透過 Gitea Runner 執行 Ansible Playbook (deploy-ops-tools.yml) 安裝與更新目標節點工具鏈",
            workflow_file="deploy-ops-tools.yml",
            playbook_path="playbooks/deploy-ops-tools.yml"
        ))

        # Step 0.3: Deploy Node SSH Keys via Runner Playbook
        self.register(SetupStep(
            step_id="deploy_node_ssh_keys",
            name="0.3 派發節點 SSH 金鑰與連線組態同步 (~/.ssh/)",
            description="透過 Gitea Runner 執行 Ansible Playbook (deploy-node-ssh-keys.yml) 部署目標節點 authorized_keys 與管理私鑰",
            workflow_file="deploy-ssh-keys.yml",
            playbook_path="playbooks/deploy-node-ssh-keys.yml"
        ))

        # Step 1: System Base Provisioning (全網伺服器基線設定、容器環境與 Hook 掛載)
        self.register(SetupStep(
            step_id="system_base_provisioning",
            name="1. 伺服器節點基線設定與容器環境掛載 (Node Provisioning & Hooks)",
            description="全網伺服器安裝 common_packages、時區語系配置與 Docker Compose Hook 掛載",
            workflow_file="system-base-setup.yml",
            playbook_path="playbooks/node-provisioning.yml",
            enabled=True
        ))

        # Step 2: Pull Docker Compose
        self.register(SetupStep(
            step_id="pull_docker_compose",
            name="2. 同步 Docker Compose 倉庫 (Docker Hosts)",
            description="拉取最新 Docker Compose 設定檔至 受控伺服器節點",
            workflow_file="pull-docker-compose.yml",
            playbook_path="playbooks/pull-docker-compose.yml"
        ))

        # Step 3: Ansible SSH Key Rotation
        self.register(SetupStep(
            step_id="rotate_ansible_keys",
            name="3. 派發/輪換 Ansible 自動化管理金鑰",
            description="執行三階段 Ansible 自動化連線金鑰輪換與同步",
            workflow_file="rotate-ansible-keys.yml",
            playbook_path="playbooks/rotate-ansible-keys.yml"
        ))

        # Step 4: Storage & Appliance SSH Key Rotation
        if get_cluster_prefix() != "openlab":
            self.register(SetupStep(
                step_id="rotate_storage_keys",
                name="4. 派發/輪換 儲存與底層設備 SSH 連線金鑰",
                description="執行三階段 Storage 與 Virtualization 設備連線金鑰輪換",
                workflow_file="rotate-storage-keys.yml",
                playbook_path="playbooks/rotate-storage-keys.yml"
            ))

        # Step 5: Generic Host SSH Key Setup & Deployment ($hostname.pub / WSL 自動偵測)
        self.register(SetupStep(
            step_id="deploy_host_key",
            name="5. 產生當前端點主機 ($hostname.pub / WSL 自動辨識) SSH Key 並部署至伺服器",
            description="生成 $hostname.key/$hostname.pub (WSL 內核自動命名)，同步至 openlab-secrets 並部署至各伺服器 labadmin 帳號",
            workflow_file="deploy-host-key.yml",
            playbook_path="playbooks/deploy-host-key.yml"
        ))

        # Step 6: [非核心擴充] Admin SSH 2FA (純內網環境已除役，作為非核心擴充)
        self.register(SetupStep(
            step_id="harden_ssh_2fa",
            name="6. [非核心擴充] 啟用管理者帳號 SSH 雙重認證 (公鑰 + 密碼)",
            description="sshd 加入 Match User admin: AuthenticationMethods publickey,password（純內網環境已除役）",
            workflow_file="harden-ssh-2fa.yml",
            playbook_path="playbooks/harden-ssh-2fa.yml",
            enabled=False
        ))

        # 預留未來的擴充步驟範例 (可隨時啟用或透過 plugin 載入)
        self.register(SetupStep(
            step_id="security_firewall_setup",
            name="7. [預留擴充] 防火牆與 SSH 存取限制硬化",
            description="設定 iptables / ufw / nftables 白名單",
            workflow_file="security-hardening.yml",
            playbook_path="playbooks/security-hardening.yml",
            enabled=False  # 待未來整合時開啟
        ))

    def get_enabled_steps(self) -> List[SetupStep]:
        return [step for step in self.steps.values() if step.enabled]


def interactive_menu(registry: ServerSetupRegistry, mode: str = "gitea"):
    """互動式選單模式"""
    while True:
        from core.version import get_local_version
        local_ver = get_local_version()
        ui_header(f"OpenLabOps Server Setup & Integration Trigger Suite (v{local_ver})")
        ui_kv("控制台端點", socket.gethostname())
        ui_kv("工具版本", f"v{local_ver}")
        ui_kv("預設派發模式", "Gitea CI Runner" if mode == "gitea" else "Ansible Local")
        ui_divider()

        enabled_steps = registry.get_enabled_steps()
        options = [f"{step.name}" for step in enabled_steps]
        options.append("🚀 [一鍵全自動執行] 依序執行上述所有整合 Trigger")
        options.append("🔄 切換派發模式 (Gitea CI / 本地 Ansible)")
        options.append("❌ 退出 Setup 控制台")

        choice_idx, selected = ui_select("請選取 Server Setup 觸發項目:", options)

        if choice_idx <= len(enabled_steps):
            target_step = enabled_steps[choice_idx - 1]
            if ui_confirm(f"確定要執行 [{target_step.name}] 嗎？", "y"):
                target_step.run(mode=mode)
        elif choice_idx == len(enabled_steps) + 1:
            if ui_confirm("確定要按順序執行所有已啟用的 Setup Trigger 步驟嗎？", "y"):
                ui_info("開始進行一鍵全自動 Server Setup 流程...")
                for step in enabled_steps:
                    ui_divider()
                    success = step.run(mode=mode)
                    if not success:
                        ui_warn(f"步驟 [{step.step_id}] 執行中斷，終止後續流程。")
                        break
                ui_success("所有 Setup 流程執行完畢！")
        elif choice_idx == len(enabled_steps) + 2:
            mode = "local" if mode == "gitea" else "gitea"
            ui_info(f"已切換派發模式為: {mode}")
        elif choice_idx == len(enabled_steps) + 3:
            ui_info("已退出 Server Setup 控制台。")
            break


def run_full_system_setup(target_hosts: str = "servers", mode: str = "gitea") -> bool:
    """執行全域基線更新與全節點 IaC 套用 (預設模式)"""
    ui_header(f"🚀 全網伺服器基線更新與容器環境掛載 (目標: {target_hosts})")
    if mode == "gitea":
        ui_info("正在向 Gitea Actions 派發 system-base-setup 工作流...")
        return gitea_dispatch("system-base-setup.yml", {
            "ref": "main",
            "inputs": {"target_hosts": target_hosts}
        })
    else:
        candidate_roots = [
            Path(__file__).resolve().parent.parent.parent / "ansible",
            Path.home() / "openlab-ansible",
            Path.home() / "openlabops" / "ansible",
        ]
        ansible_root = next((p for p in candidate_roots if (p / "inventory" / "hosts.yml").exists()), candidate_roots[0])
        cmd_list = [
            "ansible-playbook",
            "-i", str(ansible_root / "inventory" / "hosts.yml"),
            str(ansible_root / "playbooks" / "node-provisioning.yml"),
            "--extra-vars", f"target_hosts={target_hosts}"
        ]
        ui_info(f"執行本地 Ansible 指令: {' '.join(cmd_list)}")
        return subprocess.run(cmd_list).returncode == 0


def main(args_list=None):
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="lab-setup", description=t("setup.cli_desc", "OpenLabOps Server Setup Trigger CLI (lab-setup)"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-l", "--list", action="store_true", help=t("setup.cli_list", "List all registered Setup Trigger steps"))
    parser.add_argument("-p", "--provision", action="store_true", help=t("setup.cli_provision", "Run baseline provisioning and container setup across server fleet"))
    parser.add_argument("-t", "--target", type=str, default="servers", help=t("setup.cli_target", "Target server group (default: servers)"))
    parser.add_argument("-a", "--all", action="store_true", help=t("setup.cli_all", "Execute all enabled Setup Trigger steps sequentially"))
    parser.add_argument("-s", "--step", type=str, help=t("setup.cli_step", "Execute a specific Step ID (e.g. system_base_provisioning, pull_docker_compose)"))
    parser.add_argument("-m", "--mode", choices=["gitea", "local"], default="gitea", help=t("setup.cli_mode", "Execution mode: gitea (default) or local"))

    args = parser.parse_args(args_list)

    if args.version:
        from core.version import print_version
        print_version("OpenLabOps Server Setup Suite (lab-setup)")
        return

    if args.provision:
        ok = run_full_system_setup(target_hosts=args.target, mode=args.mode)
        sys.exit(0 if ok else 1)

    registry = ServerSetupRegistry()

    if args.list:
        ui_header("已註冊的 Server Setup Triggers 列表")
        for step_id, step in registry.steps.items():
            status = "✅ 啟用" if step.enabled else "⏸️ 預留/停用"
            print(f"[{step_id:25s}] {status} - {step.name}")
            print(f"  └─ 說明: {step.description}")
        return

    if args.step:
        if args.step in registry.steps:
            step = registry.steps[args.step]
            ok = step.run(mode=args.mode)
            sys.exit(0 if ok else 1)
        else:
            ui_warn(f"找不到指定的 Step ID: {args.step}")
            print("可用的 Step IDs:", ", ".join(registry.steps.keys()))
            sys.exit(1)

    if args.all:
        enabled_steps = registry.get_enabled_steps()
        ui_info("依序派發所有 Server Setup Trigger 步驟...")
        all_ok = True
        for step in enabled_steps:
            if not step.run(mode=args.mode):
                all_ok = False
        sys.exit(0 if all_ok else 1)

    # 預設無參數時進入互動式選單
    interactive_menu(registry, mode=args.mode)


if __name__ == "__main__":
    main()
