#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Cluster Management Console (lab-node)
節點動態納管與引導模組 (Day-0 Bootstrap & Day-2 Node Ingestion):
1. 互動式遠端連線建立與開門公鑰注入 (Bootstrap SSH Key & Sudoers)
2. 注入執行輕量事實採集腳本 (bootstrap_probe.sh)
3. 本地與全網節點快照更新 (current.json)
4. 調用分類引擎自動預分類 (hosts.yml)
5. 提交節點審計事實至 Gitea (openlab-configs) 並觸發 Ansible 納管
"""

import os
import sys
import json
import re
import socket
import base64
import shutil
import argparse
import subprocess
from pathlib import Path
import urllib.request
import urllib.error

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.ui_menu import ui_select, ui_confirm, ui_form, select_target_hosts
from core.config import get_admin_user, get_ansible_user, get_cluster_targets, get_manifest_path, is_openlab
from core.version import get_local_version
from core.i18n import t

candidate_ops_dirs = [
    Path.cwd(),
    Path.home() / "openlabops",
    Path.home() / "openlab-operations",
    Path(__file__).resolve().parent.parent.parent,
    Path(__file__).resolve().parent.parent,
    Path("/usr/local/bin/openlab"),
]
OPS_DIR = next(
    (d for d in candidate_ops_dirs if (d / "conf" / "nodes").exists() and (d / "ansible" / "inventory").exists()),
    next((d for d in candidate_ops_dirs if (d / "conf" / "nodes").exists() or (d / "engine").exists()), candidate_ops_dirs[0])
)
for _d in candidate_ops_dirs:
    if (_d / "engine").exists() and str(_d) not in sys.path:
        sys.path.insert(0, str(_d))
BASE_DIR = OPS_DIR.parent
PROBE_SCRIPT = OPS_DIR / "engine" / "bootstrap_probe.sh"
if not PROBE_SCRIPT.exists():
    for _d in candidate_ops_dirs:
        if (_d / "engine" / "bootstrap_probe.sh").exists():
            PROBE_SCRIPT = _d / "engine" / "bootstrap_probe.sh"
            break
if not PROBE_SCRIPT.exists():
    PROBE_SCRIPT = Path(__file__).resolve().parent / "bootstrap_probe.sh"

SNAPSHOT_PATHS = [
    OPS_DIR / "conf" / "nodes" / "current.json",
    OPS_DIR / "tools" / "conf" / "current.json",
    Path.home() / "openlabops" / "conf" / "nodes" / "current.json",
    Path("/usr/local/bin/openlab/conf/current.json"),
]


def get_current_snapshot() -> list:
    """
    動態載入全網節點清單 (100% Dynamic Facts SSOT):
    1. 優先直接自目前專案 conf/nodes/*.json 即時聚合掃描 (扣除 current.json 與 archive)。
       若目錄存在，即使納管節點為 0 台亦以此即時事實為唯一真相，絕不 fallback 讀取陳舊快照。
    2. 若未處於專案源碼庫環境（如獨立終端工具環境），則依序讀取 SNAPSHOT_PATHS 之 current.json。
    """
    # 1. 優先即時動態掃描 conf/nodes/*.json
    for nodes_dir in [OPS_DIR / "conf" / "nodes", Path.home() / "openlabops" / "conf" / "nodes"]:
        if nodes_dir.exists():
            nodes = []
            for nf in sorted(nodes_dir.glob("*.json")):
                if nf.name in ("current.json", "archive") or nf.name.startswith("."):
                    continue
                try:
                    data = json.loads(nf.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        nodes.append(data)
                except Exception:
                    pass
            return nodes

    # 2. 備援：自快照路徑載入
    for p in SNAPSHOT_PATHS:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
    return []


def save_current_snapshot(nodes: list):
    """更新全網節點快照 current.json"""
    json_str = json.dumps(nodes, indent=2, ensure_ascii=False) + "\n"
    for p in SNAPSHOT_PATHS:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        except PermissionError:
            pass


def list_nodes():
    """顯示已納管節點清冊 (比對遠端與本機快取，一致則秒讀快取，不一致自動同步)"""
    ui_header(f"OpenLabOps 已納管節點清單 (lab-node list v{get_local_version()})")
    from core.gitea_api import sync_remote_node_cache_if_needed
    nodes, source_label, is_online = sync_remote_node_cache_if_needed()
    if not is_online and not nodes:
        ui_error("離線狀態：無法連線至 Gitea 聯邦倉庫取得節點事實。")
        return
    if not nodes:
        ui_warn("遠端聯邦倉庫目前尚未有任何節點事實紀錄。可執行 `lab-node add <IP>` 進行納管。")
        return

    print(f"{'主機名稱':<12} {'主要 IP':<16} {'節點類別':<14} {'作業系統/韌體':<22} {'核心/記憶體':<14} {'Docker 容器':<10}")
    print("-" * 90)
    for n in nodes:
        h = n.get("hostname", "unknown")
        ip = n.get("primary_ip", "unknown")
        cat = n.get("node_category", "server")
        if cat == "hypervisor":
            cat_str = "🖥️ Hypervisor"
        elif cat == "appliance":
            cat_str = "📦 Appliance"
        elif cat == "endpoint":
            cat_str = "💻 Endpoint"
        else:
            cat_str = "🌐 Server"
        os_name = n.get("distribution", n.get("os_family", "Linux"))
        hw = n.get("hardware", {})
        cores = hw.get("cpu_cores", "-")
        mem = hw.get("memory_mb", 0)
        mem_str = f"{round(mem/1024, 1)}G" if mem else "-"
        caps = n.get("capabilities", {})
        docker_str = "● 支援" if caps.get("has_docker") else "○ 無"
        print(f"{h:<12} {ip:<16} {cat_str:<14} {os_name[:20]:<22} {f'{cores}C / {mem_str}':<14} {docker_str:<10}")
    print("-" * 90)
    src_info = f" (來源: {source_label})" if source_label else ""
    ui_info(f"總計已納管節點: {len(nodes)} 台{src_info}")


def _resolve_target_ip(hname: str, host_val: str, is_local: bool = False) -> str:
    """嘗試解析節點之 IPv4 位址 (支援直連 IP、DNS/hosts、~/.ssh/config 與 manifest 查表)"""
    ipv4_re = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
    for cand in (host_val, hname):
        if cand and ipv4_re.match(cand):
            return cand

    if is_local or host_val in ("localhost", "127.0.0.1"):
        try:
            resolved = socket.gethostbyname(hname)
            if ipv4_re.match(resolved) and not resolved.startswith("127."):
                return resolved
        except Exception:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.1.1", 80))
                local_ip = s.getsockname()[0]
                if ipv4_re.match(local_ip):
                    return local_ip
        except Exception:
            pass
        return "127.0.0.1"

    for cand in (host_val, hname):
        if not cand:
            continue
        try:
            resolved = socket.gethostbyname(cand)
            if ipv4_re.match(resolved):
                return resolved
        except Exception:
            pass

    # 嘗試從 ~/.ssh/config 查 HostName
    ssh_cfg = Path.home() / ".ssh" / "config"
    if ssh_cfg.exists():
        try:
            in_block = False
            targets = {hname.lower(), (host_val or "").lower()} - {""}
            for raw in ssh_cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                low = line.lower()
                if low.startswith("host "):
                    aliases = {a.lower() for a in line.split()[1:]}
                    in_block = bool(aliases & targets)
                elif in_block and low.startswith("hostname "):
                    hn = line.split(None, 1)[1].strip()
                    if ipv4_re.match(hn):
                        return hn
        except Exception:
            pass

    # 嘗試從 manifest 查表
    manifest_path = get_manifest_path()
    if manifest_path and manifest_path.exists():
        try:
            from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata
            meta_map = extract_manifest_hosts_metadata(parse_yaml_file(manifest_path))
            for k, m in meta_map.items():
                if k.lower() == hname.lower() or k.split(".")[0].lower() == hname.lower():
                    mip = str(m.get("ip", "")).strip()
                    if ipv4_re.match(mip):
                        return mip
        except Exception:
            pass

    return ""


def _build_node_fact_from_target(target: dict) -> dict | None:
    """將 tools.config.json / manifest 靜態目標轉換為符合 schema/nodes.cue 的節點事實物件"""
    hname = str(target.get("name", "")).strip()
    if not hname:
        return None
    host_val = str(target.get("host", hname)).strip()
    is_local = bool(target.get("is_local")) or host_val in ("localhost", "127.0.0.1") or hname == "control-node"
    primary_ip = _resolve_target_ip(hname, host_val, is_local=is_local)
    if not primary_ip:
        return None

    os_str = str(target.get("os", "Linux")).strip()
    mgr = str(target.get("mgr", "")).strip().lower()
    os_low = os_str.lower()

    if is_local:
        node_class = "standard"
        node_category = "dev"
        appliance_type = "none"
        key_profile = "standard"
        is_immutable = False
        always_online = True
    elif mgr == "vib" or target.get("is_kvm"):
        node_class = "appliance"
        node_category = "hypervisor"
        appliance_type = "kvm"
        key_profile = "standard"
        is_immutable = True
        always_online = True
    elif mgr == "firmware" or target.get("is_storage"):
        node_class = "appliance"
        node_category = "storage"
        appliance_type = "storage"
        key_profile = "standard"
        is_immutable = True
        always_online = True
    else:
        node_class = "standard"
        node_category = str(target.get("role", "server")).strip() or "server"
        if node_category not in ("dev", "server", "desktop"):
            node_category = "server"
        appliance_type = "none"
        key_profile = "standard"
        is_immutable = False
        always_online = (node_category != "desktop")

    if "arch" in os_low:
        os_family = "ArchLinux"
    elif "photon" in os_low:
        os_family = "PhotonOS"
    elif "oracle" in os_low:
        os_family = "OracleLinux"
    elif "ubuntu" in os_low:
        os_family = "Ubuntu"
    elif "debian" in os_low:
        os_family = "Debian"
    elif "alpine" in os_low:
        os_family = "Alpine"
    elif appliance_type == "kvm":
        os_family = "Virtualization"
    else:
        os_family = os_str.split()[0] if os_str else "Linux"

    domain = "lab" if is_openlab() else "openlab.com"
    fqdn = hname if "." in hname else f"{hname}.{domain}"
    subnet_cidr = f"{primary_ip.rsplit('.', 1)[0]}.0/24"
    return {
        "hostname": hname,
        "fqdn": fqdn,
        "primary_ip": primary_ip,
        "subnet_cidr": subnet_cidr,
        "node_class": node_class,
        "node_category": node_category,
        "always_online": always_online,
        "is_immutable": is_immutable,
        "appliance_type": appliance_type,
        "key_profile": key_profile,
        "os_family": os_family,
        "distribution": os_str or os_family,
        "capabilities": {
            "has_docker": False,
            "has_python": appliance_type not in ("kvm", "storage"),
        },
    }


def sync_nodes_to_federation(dry_run: bool = False, emit=None) -> bool:
    """比對本機節點設定與遠端 Gitea 聯邦倉庫，將本機有但遠端缺少的節點自動推送註冊，並重新編譯快照"""
    log = emit or print
    from core.gitea_api import sync_remote_node_cache_if_needed, register_node_fact_via_runner

    # 1. 收集本機節點資料 (優先 conf/nodes/*.json，並補齊 tools.config.json / manifest 靜態目標，不觸發遠端快取)
    local_by_key = {}
    for n in get_current_snapshot():
        h = str(n.get("hostname", "")).strip()
        if h:
            local_by_key[h.split(".")[0].lower()] = n

    unresolved = []
    for tgt in get_cluster_targets(include_remote_cache=False):
        h = str(tgt.get("name", "")).strip()
        if not h:
            continue
        short_k = h.split(".")[0].lower()
        if short_k not in local_by_key:
            built = _build_node_fact_from_target(tgt)
            if built:
                local_by_key[short_k] = built
            else:
                unresolved.append(h)

    # 2. 取得遠端聯邦倉庫事實 (透過快取比對，避免重複派發 Runner)
    remote_nodes, source_label, is_online = sync_remote_node_cache_if_needed()
    if not is_online:
        log("[!] 無法取得遠端節點清冊（Gitea 離線或 Runner 逾時），已中止同步以避免誤判。")
        return False

    remote_keys = set()
    for n in remote_nodes:
        rh = str(n.get("hostname", "")).strip().lower()
        if rh:
            remote_keys.add(rh)
            remote_keys.add(rh.split(".")[0])

    missing_in_remote = [
        node for k, node in local_by_key.items()
        if k not in remote_keys and str(node.get("hostname", "")).lower() not in remote_keys
    ]

    log(f"本機節點清冊: {len(local_by_key)} 台 | 遠端聯邦倉庫: {len(remote_nodes)} 台 ({source_label})")
    if unresolved:
        log(f"[!] 下列本機目標無法解析 IPv4 位址，已略過: {', '.join(unresolved)}")

    if not missing_in_remote:
        log("[✓] 本機與遠端聯邦倉庫節點清冊已一致，無需推送新節點。")
    else:
        names = ", ".join(f"{n['hostname']}({n['primary_ip']})" for n in missing_in_remote)
        log(f"[*] 發現 {len(missing_in_remote)} 台本機節點尚未註冊至遠端倉庫: {names}")
        if dry_run:
            log("[DRY-RUN] 僅預覽差異，未執行遠端寫入。")
            return True

        all_ok = True
        for node in missing_in_remote:
            hname = node["hostname"]
            log(f" -> 正在派發 register-node-fact.yml 註冊 {hname} ({node['primary_ip']})...")
            ok = register_node_fact_via_runner(hname, node, action="upsert", wait=True)
            if ok:
                log(f"    [✓] {hname} 已寫入遠端聯邦倉庫")
            else:
                log(f"    [✗] {hname} 寫入遠端聯邦倉庫失敗")
                all_ok = False
        if not all_ok:
            return False

    # 3. 同步更新本地快照與 inventory (若有 classifier.py)
    classifier_script = OPS_DIR / "engine" / "classifier.py"
    if classifier_script.exists():
        log("[*] 正在執行 classifier.py --apply --sync-tools 更新本地快照...")
        res = subprocess.run([sys.executable, str(classifier_script), "--apply", "--sync-tools"], capture_output=True, text=True)
        if res.returncode == 0:
            log("[✓] 本地快照與庫存同步完成！")
        else:
            log(f"[!] classifier.py 執行警告: {res.stderr.strip() or res.stdout.strip()}")
    return True


def load_bootstrap_pubkey(automation_user: str = None) -> str:
    """讀取本機用於開門之自動化公鑰"""
    automation_user = automation_user or get_ansible_user()
    candidates = [
        Path.home() / ".ssh" / f"{automation_user}.pub",
        Path.home() / ".ssh" / "ansible.key.pub",
        Path.home() / ".ssh" / "openlab_bootstrap.pub",
        Path.home() / ".ssh" / "id_ed25519.pub",
        BASE_DIR / "openlab-secrets" / "ssh-key" / f"{automation_user}.pub"
    ]
    for c in candidates:
        if c.exists():
            return c.read_text(encoding="utf-8").strip()
    return ""


def run_node_onboarding(
    target_ip: str,
    ssh_port: int = 22,
    login_user: str = "root",
    automation_user: str = None,
    key_file: str = None,
    password: str = None,
    node_category: str = None,
    always_online: bool = None,
    appliance_type: str = "none"
):
    """執行單一節點開門、審計探測與全網納管閉環"""
    automation_user = automation_user or get_ansible_user()
    ui_header(f"節點引導與動態納管精靈 (lab-node add v{get_local_version()})")
    ui_kv("目標位址", f"{target_ip}:{ssh_port}")
    ui_kv("初始登入帳號", login_user)
    ui_kv("自動化開門目標", f"帳號 '{automation_user}'")
    if key_file:
        ui_kv("初始連線私鑰", key_file)
    if node_category:
        ui_kv("指定節點類別", node_category)
    if always_online is not None:
        ui_kv("常態在線 (7/24)", "是" if always_online else "否")

    ui_kv("引導金鑰模式", "臨時安全金鑰 (完成後由 Runner 自 *-secrets 部署正式公鑰)")
    ui_divider()

    if not PROBE_SCRIPT.exists():
        ui_error(f"找不到注入腳本: {PROBE_SCRIPT}")
        return False

    script_content = PROBE_SCRIPT.read_text(encoding="utf-8")

    # 1. 委派 engine.onboard.onboard_node 執行 PTY 開門與探測
    ui_info(f"正在與目標主機 {target_ip} 建立 SSH 連線並注入引導腳本 (PTY 模擬與即時認證)...")
    if str(OPS_DIR) not in sys.path:
        sys.path.insert(0, str(OPS_DIR))
    from engine.onboard import onboard_node, get_default_homelab_subnets

    active_subnets = get_default_homelab_subnets()

    ok, facts_or_err = onboard_node(
        host=target_ip,
        user=login_user,
        port=ssh_port,
        password=password,
        key_file=os.path.expanduser(key_file) if key_file else None,
        target_user=automation_user,
        allowed_subnets=active_subnets,
        interactive=True,
        callback=lambda msg: ui_info(msg.strip()),
        node_category=node_category,
        always_online=always_online
    )

    if not ok or not isinstance(facts_or_err, dict):
        ui_error(f"遠端引導執行失敗: {facts_or_err}")
        return False

    node_fact = facts_or_err
    if node_category:
        node_fact["node_category"] = node_category
    if always_online is not None:
        node_fact["always_online"] = always_online
    if appliance_type and appliance_type != "none":
        node_fact["appliance_type"] = appliance_type

    hname = node_fact.get("hostname", "")
    os_name = node_fact.get("distribution", node_fact.get("os_family", "Linux"))
    ui_success(f"成功開門並取得節點事實: {hname} ({os_name}) | IP: {node_fact.get('primary_ip')}")

    # 3. 固化個別節點 Inventory 分類 JSON (conf/nodes/<hostname>.json，僅保留 Inventory 分類欄位，不觸碰 node-information/)
    nodes_dir = OPS_DIR / "conf" / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    caps = node_fact.get("capabilities", {})
    clean_fact = {
        "hostname": hname,
        "fqdn": node_fact.get("fqdn") or f"{hname}.lab",
        "primary_ip": node_fact.get("primary_ip", target_ip),
        "subnet_cidr": node_fact.get("subnet_cidr") or f"{target_ip.rsplit('.', 1)[0]}.0/24",
        "node_category": node_fact.get("node_category", "server"),
        "always_online": bool(node_fact.get("always_online", True)),
        "is_immutable": bool(node_fact.get("is_immutable", False)),
        "appliance_type": node_fact.get("appliance_type", "none"),
        "key_profile": node_fact.get("key_profile", "standard"),
        "os_family": node_fact.get("os_family", "Linux"),
        "distribution": os_name,
        "capabilities": {
            "has_docker": bool(caps.get("has_docker", False)),
            "has_python": bool(caps.get("has_python", True))
        }
    }
    single_node_file = nodes_dir / f"{hname}.json"
    single_node_file.write_text(json.dumps(clean_fact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ui_info(f"已儲存單一節點分類檔: {single_node_file}")

    # 4. 重新觸發分類與快照聚合
    classifier_script = OPS_DIR / "engine" / "classifier.py"
    if classifier_script.exists():
        ui_info("正在重新計算預分類與全網快照 (classifier.py --apply)...")
        res = subprocess.run([sys.executable, str(classifier_script), "--apply", "--sync-tools"], capture_output=True, text=True)
        if res.returncode == 0:
            ui_success("inventory/hosts.yml 與 current.json 已自動更新！")
        else:
            ui_warn(f"分類引擎警示: {res.stderr}")

    # 5. 透過 ci-bot 派發 register-node-fact.yml 與 deploy-ssh-keys.yml 至聯邦倉庫
    try:
        from core.gitea_api import gitea_dispatch, register_node_fact_via_runner
        ui_info(f"正在派發 register-node-fact.yml，由 Runner 將 [{hname}] 註冊至聯邦倉庫...")
        register_node_fact_via_runner(hname, clean_fact, action="upsert", wait=True)
        ui_info(f"正在派發 deploy-ssh-keys.yml，由 Runner 自 *-secrets 部署正式公鑰至 [{hname}]...")
        gitea_dispatch(
            "deploy-ssh-keys.yml",
            payload={
                "ref": "main",
                "inputs": {
                    "target_hosts": hname,
                    "target_user": automation_user,
                    "deploy_authorized_keys": "true",
                    "deploy_client_keys": "false",
                },
            },
            wait=True,
        )
    except Exception:
        pass

    cat = node_fact.get("node_category", "server")
    is_imm = node_fact.get("is_immutable", False)
    app_t = node_fact.get("appliance_type", "none")

    if is_imm or cat in ["appliance", "hypervisor"]:
        ui_warn(f"此節點識別為嵌入式韌體/不可變虛擬化底座 ({cat}: {app_t})。")
        ui_info("無須執行標準 node-provisioning.yml，Ansible 將自動透過專屬角色進行安全維運。")
    else:
        if ui_confirm(f"是否立即透過 Ansible 執行 node-provisioning.yml 對 [{hname}] 進行環境標準化？", "y"):
            ansible_hosts_file = BASE_DIR / "openlab-ansible" / "inventory" / "hosts.yml"
            if not ansible_hosts_file.exists():
                ansible_hosts_file = OPS_DIR / "ansible" / "inventory" / "hosts.yml"
            ansible_pb = BASE_DIR / "openlab-ansible" / "playbooks" / "node-provisioning.yml"
            if not ansible_pb.exists():
                ansible_pb = OPS_DIR / "ansible" / "playbooks" / "node-provisioning.yml"
            if ansible_hosts_file.exists() and ansible_pb.exists():
                ui_info(f"正在執行: ansible-playbook -i {ansible_hosts_file} {ansible_pb} -e target_hosts={hname}...")
                subprocess.run(["ansible-playbook", "-i", str(ansible_hosts_file), str(ansible_pb), "-e", f"target_hosts={hname}"])

    return True


def revoke_remote_management_key(host: str, target_user: str = None, timeout: int = 8) -> bool:
    """連線至遠端節點，自其 ~/.ssh/authorized_keys 中收回管理端公鑰（委派 engine.onboard [ARCH-03]）"""
    target_user = target_user or get_ansible_user()
    if str(OPS_DIR) not in sys.path:
        sys.path.insert(0, str(OPS_DIR))
    try:
        from engine.onboard import revoke_remote_management_key as _engine_revoke
        return _engine_revoke(host, target_user=target_user, timeout=timeout)
    except ImportError:
        return False


def remove_node(target: str, force: bool = False, purge: bool = False, no_revoke: bool = False) -> bool:
    """從叢集中解除管控、下架節點並處理事實配置與備份檔案（委派 engine.onboard.decommission_node [ARCH-03]）"""
    ui_header(f"節點除役與脫離管控精靈 (lab-node remove v{get_local_version()})")
    if not force:
        if not ui_confirm(f"確定要將節點 [{target}] 解除管控並自叢集中除役？", "n"):
            ui_warn("使用者取消除役動作。")
            return False

    purge_data = purge
    if not force and not purge:
        if not ui_confirm(f"是否保留節點 [{target}] 的歷史備份與遙測記錄？ (Y: 封存保留, N: 徹底清除)", "y"):
            purge_data = True

    if str(OPS_DIR) not in sys.path:
        sys.path.insert(0, str(OPS_DIR))
    try:
        from engine.onboard import decommission_node
        target_account = get_ansible_user()
        return decommission_node(
            target=target,
            target_user=target_account,
            purge=purge_data,
            no_revoke=no_revoke,
            callback=lambda msg: ui_info(msg.strip())
        )
    except ImportError as e:
        ui_error(f"無法載入 engine.onboard: {e}")
        return False


def interactive_menu():
    """TUI 互動選單進入點"""
    while True:
        ui_header(f"節點動態納管控制台 (lab-node v{get_local_version()})")
        options = [
            "🚀 [Add] 納管全新節點 (開門、探測與預分類)",
            "📋 [List] 檢視目前全網已納管節點清單",
            "🗑️ [Remove] 解除管控節點 (收回公鑰、除役並更新庫存)",
            "🔄 [Sync] 重新計算全網節點預分類與快照",
            "❌ 離開"
        ]
        choice_idx, _ = ui_select("請選擇節點納管任務:", options)

        if choice_idx == 1:
            ui_header("🚀 步驟 1/3: 選擇節點系統類別 (Node Architecture Class)")
            sys_classes = [
                "🐧 標準通用作業系統 (Standard Linux Servers & Desktops)",
                "⬅️ 返回"
            ]
            class_idx, _ = ui_select("請選擇該節點之架構大類:", sys_classes)
            if class_idx == 0 or class_idx == 2:
                continue

            node_category = "server"
            always_online = True
            appliance_type = "none"

            if class_idx == 1:
                sub_classes = [
                    "🖥️ Server (常態服務伺服器，7/24 在線)",
                    "💻 Desktop (客戶端工作站/筆電，非常態在線，開機金鑰同步門禁)",
                    "🛠️ Dev (本專案開發控制台，7/24 在線，持有維運私鑰)"
                ]
                sub_idx, _ = ui_select("請選擇標準系統之角色大類:", sub_classes)
                if sub_idx == 1:
                    node_category = "server"
                    always_online = True
                elif sub_idx == 2:
                    node_category = "desktop"
                    always_online = False
                elif sub_idx == 3:
                    node_category = "dev"
                    always_online = True
            admin_usr = get_admin_user()
            ansible_usr = get_ansible_user()
            default_login_user = admin_usr if node_category == "desktop" else "root"
            from core.ui_menu import ui_form
            form_fields = [
                {"key": "target_ip", "label": "目標節點 IP 位址", "value": "192.168.1.50"},
                {"key": "ssh_port", "label": "SSH 連線埠號", "value": "22"},
                {"key": "login_user", "label": "初始登入帳號", "value": default_login_user},
                {"key": "key_file", "label": "初始登入私鑰 (可留空使用密碼)", "value": ""},
                {"key": "password", "label": "初始登入 / Sudo 密碼 (可留空)", "value": "", "secret": True},
                {"key": "auto_user", "label": "建立自動化帳號", "value": ansible_usr},
            ]
            res = ui_form(f"🚀 步驟 2/3: 填寫連線參數 ({node_category.upper()})", form_fields)
            if res:
                target_ip = res.get("target_ip", "").strip()
                if not target_ip:
                    ui_warn("未輸入 IP，略過。")
                    continue
                ssh_port_str = str(res.get("ssh_port", 22)).strip() or "22"
                login_user = res.get("login_user", default_login_user).strip() or default_login_user
                key_file = res.get("key_file", "").strip() or None
                password = res.get("password", "").strip() or None
                auto_user = res.get("auto_user", ansible_usr).strip() or ansible_usr
                run_node_onboarding(
                    target_ip, int(ssh_port_str), login_user, auto_user,
                    key_file=key_file,
                    password=password,
                    node_category=node_category,
                    always_online=always_online,
                    appliance_type=appliance_type
                )
            input("\n按 Enter 鍵返回選單...")

        elif choice_idx == 2:
            list_nodes()
            input("\n按 Enter 鍵返回選單...")

        elif choice_idx == 3:
            from core.ui_menu import select_target_hosts
            targets = select_target_hosts("請選擇欲解除管控與除役之節點", default_all=False)
            if targets:
                for tgt in targets:
                    remove_node(tgt)
            else:
                ui_warn("未選取任何節點，略過。")
            input("\n按 Enter 鍵返回選單...")

        elif choice_idx == 4:
            ui_info("正在比對本機節點與遠端聯邦倉庫並執行同步...")
            sync_nodes_to_federation(emit=print)
            input("\n按 Enter 鍵返回選單...")

        elif choice_idx == 5 or choice_idx == 0:
            break


def main():
    from core.lockout import enforce_lockout_guard
    enforce_lockout_guard("lab-node")

    # 無參數且支援 Curses 時，優先啟動與 lab-init 統一之 BSDInstall TUI
    if len(sys.argv) == 1:
        try:
            if str(OPS_DIR) not in sys.path:
                sys.path.insert(0, str(OPS_DIR))
            from engine.bsd_dialog import is_bsd_tui_supported
            from engine.onboard import run_lab_node_tui
            if is_bsd_tui_supported():
                run_lab_node_tui()
                return
        except ImportError:
            pass

    # 兼容母體 engine/onboard.py 旗標 (--manifest, --host, --remove, --classify, --non-interactive, --onboard)
    onboard_flags = {"--manifest", "--host", "--remove", "--classify", "--non-interactive", "--onboard", "onboard"}
    if any(arg in onboard_flags or any(arg.startswith(f + "=") for f in onboard_flags) for arg in sys.argv[1:]):
        onboard_script = OPS_DIR / "engine" / "onboard.py"
        if onboard_script.exists():
            passed_args = [a if a != "onboard" else "--onboard" for a in sys.argv[1:]]
            os.execvp(sys.executable, [sys.executable, str(onboard_script)] + passed_args)

    parser = argparse.ArgumentParser(prog="lab-node", description=t("node.cli_desc", "OpenLabOps Node Management & Dynamic Ingestion (lab-node)"))
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Node Management (lab-node) v{get_local_version()}")
    subparsers = parser.add_subparsers(dest="subcommand", help=t("node.cli_subcmd", "Subcommands"))

    # add subcommand
    add_parser = subparsers.add_parser("add", help=t("node.cli_add", "Onboard a new node"))
    add_parser.add_argument("target_ip", nargs="?", help=t("node.cli_target_ip", "Target host IP address"))
    add_parser.add_argument("-u", "--user", default="root", help=t("node.cli_user", "Initial login user (default: root)"))
    add_parser.add_argument("-p", "--port", type=int, default=22, help=t("node.cli_port", "SSH port (default: 22)"))
    add_parser.add_argument("-a", "--automation-user", default=get_ansible_user(), help=t("node.cli_auto_user", "Automation user to create (default: ansible)"))
    add_parser.add_argument("-k", "--key", default=None, help=t("node.cli_key", "Initial SSH private key path (leave empty for password)"))
    add_parser.add_argument("-P", "--password", default=None, help=t("node.cli_password", "Initial SSH / Sudo password (optional)"))
    add_parser.add_argument("-c", "--category", choices=["dev", "server", "desktop", "appliance"], default=None, help=t("node.cli_category", "Specify node category"))
    add_parser.add_argument("--always-online", dest="always_online", action="store_true", default=None, help=t("node.cli_always_online", "Mark node as always online (24/7)"))
    add_parser.add_argument("--intermittent", dest="always_online", action="store_false", help=t("node.cli_intermittent", "Mark node as intermittent (Desktop/Laptop)"))
    add_parser.add_argument("--appliance-type", default="none", help=t("node.cli_appliance_type", "Specify embedded/appliance type (e.g. storage, kvm)"))

    # remove subcommand
    rm_parser = subparsers.add_parser("remove", help=t("node.cli_remove", "Decommission and remove a node"))
    rm_parser.add_argument("target", help=t("node.cli_rm_target", "Target node hostname or IP"))
    rm_parser.add_argument("-f", "--force", action="store_true", help=t("node.cli_rm_force", "Force removal without interactive confirmation"))
    rm_parser.add_argument("--purge", action="store_true", help=t("node.cli_rm_purge", "Purge node facts and backups (default: archive)"))
    rm_parser.add_argument("--no-revoke", action="store_true", help=t("node.cli_rm_no_revoke", "Skip revoking public keys from remote authorized_keys"))

    # list subcommand
    subparsers.add_parser("list", help=t("node.cli_list", "List managed nodes"))

    # sync subcommand
    sync_parser = subparsers.add_parser("sync", help=t("node.cli_sync", "Sync local node definitions to remote federation repo and recalculate snapshots"))
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview local vs remote node diff without pushing")

    args = parser.parse_args()

    if args.subcommand == "add":
        target = args.target_ip
        if not target:
            target = input(t("node.prompt_target_ip", "Enter target node IP address: ")).strip()
        run_node_onboarding(
            target, args.port, args.user, args.automation_user,
            key_file=args.key,
            password=args.password,
            node_category=args.category,
            always_online=args.always_online,
            appliance_type=args.appliance_type
        )
    elif args.subcommand == "remove":
        remove_node(args.target, force=args.force, purge=args.purge, no_revoke=args.no_revoke)
    elif args.subcommand == "list":
        list_nodes()
    elif args.subcommand == "sync":
        ok = sync_nodes_to_federation(dry_run=getattr(args, "dry_run", False), emit=print)
        if not ok:
            sys.exit(1)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
