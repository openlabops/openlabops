#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps - Node Classification & Snapshot Aggregator Engine
Parses individual node JSON files in conf/nodes/*.json (or imports from CMDB),
aggregates them into conf/nodes/current.json (snapshot), and renders a
hierarchical, pre-classified inventory/hosts.yml based on:
1. Automatic signature identification of appliances & immutable hypervisors
2. OS Distro Groups for mutable servers (photonos, bsd, archlinux, debian, rhel, alpine, etc.)
3. Subnet / Network Groups (service_lan, wg_lan, openlab_mesh, user_lan, etc.)
4. Capabilities Groups (docker_hosts, gateways)
5. Strict isolation of appliances and endpoints from server/distro groups

Zero External Dependencies: 100% Python 3 standard library.
"""

import sys
import os
import json
import difflib
import argparse
from pathlib import Path

OPS_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = OPS_DIR.parent
CONF_NODES_DIR = OPS_DIR / "conf" / "nodes"
CURRENT_SNAPSHOT_FILE = CONF_NODES_DIR / "current.json"

INSTALLED_TOOLS_CONF_DIR = Path("/usr/local/bin/openlab/conf")
if (OPS_DIR.parent / "openlab-ansible").exists():
    DEFAULT_HOSTS_OUT = OPS_DIR.parent / "openlab-ansible" / "inventory" / "hosts.yml"
else:
    DEFAULT_HOSTS_OUT = OPS_DIR / "ansible" / "inventory" / "hosts.yml"


# 預定義已知網段別名 (嚴格對齊 schema/network.cue 與 manifest)
KNOWN_SUBNETS = {
    "192.168.1.0/24": "flat_lan",
    "172.28.0.0/16": "service_lan",
}

def load_manifest_networks():
    """解析 Manifest 獲取宣告之網段別名對照表 (如 flat_lan, service_lan)"""
    manifest_path = OPS_DIR / "conf" / "openlab.manifest.yml"
    if not manifest_path.exists():
        return {}
    lib_dir = str(OPS_DIR / "tools" / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from core.yaml_parser import parse_yaml_file
    data = parse_yaml_file(manifest_path)
    nets = data.get("networks", {})
    mapping = {}
    if isinstance(nets, dict):
        for name, cidr in nets.items():
            if isinstance(cidr, str) and "/" in cidr and cidr not in mapping:
                mapping[cidr] = name
    return mapping


def load_manifest_metadata():
    """透過共用純標準庫 YAML 解析器 (core.yaml_parser) 獲取靜態節點之 IP、分類層級與子群組元數據"""
    manifest_path = OPS_DIR / "conf" / "openlab.manifest.yml"
    if not manifest_path.exists():
        return {}
    lib_dir = str(OPS_DIR / "tools" / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata
    return extract_manifest_hosts_metadata(parse_yaml_file(manifest_path))


def load_manifest_inventory():
    """解析 openlab.manifest.yml 獲取靜態節點與 IP 對齊清單"""
    return {k: v["ip"] for k, v in load_manifest_metadata().items()}


def get_manifest_cluster_domain():
    """獲取 Manifest 所定義之內部域名 (如 lab 或 lab)"""
    manifest_path = OPS_DIR / "conf" / "openlab.manifest.yml"
    if manifest_path.exists():
        lib_dir = str(OPS_DIR / "tools" / "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from core.yaml_parser import parse_yaml_file
        data = parse_yaml_file(manifest_path)
        cluster = data.get("cluster", {})
        if isinstance(cluster, dict) and cluster.get("domain"):
            return cluster["domain"]
    return "lab"


def detect_node_type_and_category(hname, ip, data=None, manifest_meta=None):
    """
    依系統遙測事實與 Manifest 宣告自動辨識節點類別 (Appliance / Dev / Desktop / Server)，零寫死主機名 [INV-03]。
    """
    data = data or {}
    manifest_meta = manifest_meta or {}
    sys_info = data.get("system", {})
    node_type = str(data.get("node_type") or data.get("appliance_type") or "").lower()
    os_str = str(sys_info.get("os") or data.get("distribution") or "").lower()
    hypervisor_str = str(sys_info.get("hypervisor") or "").lower()
    existing_dist = data.get("distribution") or sys_info.get("distribution") or sys_info.get("os")
    existing_os_fam = data.get("os_family")
    m_cat = data.get("node_category") or manifest_meta.get("category")
    m_sub = manifest_meta.get("subgroup", "")
    m_roles = manifest_meta.get("roles", [])

    # 3. 本專案開發與控制台 (Dev Control Stations, always_online: True)
    if m_cat == "dev":
        dist = existing_dist or ("Arch Linux" if "arch" in hname.lower() else "Ubuntu 24.04 LTS")
        os_fam = existing_os_fam or ("ArchLinux" if "arch" in dist.lower() else "Debian")
        return {
            "node_category": "dev",
            "always_online": True,
            "is_immutable": False,
            "appliance_type": "none",
            "key_profile": "standard",
            "os_family": os_fam,
            "distribution": dist
        }

    # 4. 個人管理工作站 / 非常態在線桌面 (Desktops, always_online: False)
    if m_cat == "desktop" or ip.startswith("192.168.1."):
        return {
            "node_category": "desktop",
            "always_online": False,
            "is_immutable": False,
            "appliance_type": "none",
            "key_profile": "standard",
            "os_family": existing_os_fam or "Linux",
            "distribution": existing_dist or "Linux Workstation"
        }

    # 5. 常規 Linux 伺服器 (Servers, always_online: True)
    if "gateways" in m_roles or m_sub == "linux_bsd":
        return {
            "node_category": "server",
            "always_online": True,
            "is_immutable": False,
            "appliance_type": "none",
            "key_profile": "standard",
            "os_family": "Linux",
            "distribution": sys_info.get("os") or existing_dist or "Generic Linux"
        }
    if m_sub == "photonos" or "photon" in os_str:
        return {
            "node_category": "server",
            "always_online": True,
            "is_immutable": False,
            "appliance_type": "none",
            "key_profile": "standard",
            "os_family": "PhotonOS",
            "distribution": existing_dist or "VMware Photon OS"
        }
    if m_sub in ("oci") or "oracle" in os_str:
        return {
            "node_category": "server",
            "always_online": True,
            "is_immutable": False,
            "appliance_type": "none",
            "key_profile": "standard",
            "os_family": "OracleLinux",
            "distribution": existing_dist or "Oracle Linux 9"
        }

    dist_lower = (existing_dist or os_str or "").lower()
    os_f = existing_os_fam or "Linux"
    if "photon" in dist_lower:
        os_f = "PhotonOS"
    elif "linux_bsd" in dist_lower:
        os_f = "Linux"
    elif "arch" in dist_lower:
        os_f = "ArchLinux"
    elif "debian" in dist_lower or "ubuntu" in dist_lower:
        os_f = "Debian"
    elif "oracle" in dist_lower or "rhel" in dist_lower or "centos" in dist_lower or "rocky" in dist_lower:
        os_f = "OracleLinux"
    elif "alpine" in dist_lower:
        os_f = "Alpine"
    elif "suse" in dist_lower:
        os_f = "Suse"

    return {
        "node_category": "server",
        "always_online": True,
        "is_immutable": False,
        "appliance_type": "none",
        "key_profile": "standard",
        "os_family": os_f,
        "distribution": existing_dist or os_f
    }


def classify_node(hname, data=None, manifest_meta=None):
    """
    封裝對齊：依遙測事實識別單一節點之屬性與分類特徵 [INV-03, INV-04]
    """
    data = data or {}
    ip = data.get("primary_ip") or data.get("ansible_host") or ""
    return detect_node_type_and_category(hname, ip, data=data, manifest_meta=manifest_meta)


def load_node_files(write_back=False):
    """
    動態載入 conf/nodes/ 下所有單一節點 JSON (100% Dynamic Facts SSOT)。
    節點清單完全由 conf/nodes/*.json 決定，絕不擅自注入未經納管之靜態節點。
    """
    CONF_NODES_DIR.mkdir(parents=True, exist_ok=True)
    cmdb_dir = BASE_DIR / "openlab-configs" / "node-information"
    manifest_meta_all = load_manifest_metadata()

    nodes = []
    seen = set()

    # 1. 嚴格以 conf/nodes/*.json 現存檔案為唯一真相源
    for nf in sorted(CONF_NODES_DIR.glob("*.json")):
        if nf.name in ("current.json", "archive") or nf.name.startswith("."):
            continue
        try:
            node_data = json.loads(nf.read_text(encoding="utf-8"))
            hname = node_data.get("hostname", nf.stem)
            if not hname or hname in seen:
                continue

            ip = node_data.get("primary_ip") or node_data.get("ansible_host") or ""
            m_meta = manifest_meta_all.get(hname, {"ip": ip, "path": ["servers"]})

            # 結合 CMDB 探測資訊富化 (若存在)
            candidates = [
                cmdb_dir / f"node_{hname}.json",
                cmdb_dir / f"node_{hname.replace('_', '-')}.json"
            ]
            cmdb_file = next((c for c in candidates if c.exists()), None)
            cmdb_data = {}
            if cmdb_file:
                try:
                    cmdb_data = json.loads(cmdb_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            merged_for_detect = {**node_data, **cmdb_data}
            traits = detect_node_type_and_category(hname, ip, merged_for_detect, m_meta)

            has_docker = node_data.get("capabilities", {}).get("has_docker")
            if has_docker is None:
                has_docker = bool(cmdb_data.get("docker", {}).get("containers", []))

            prefix = ip.rsplit(".", 1)[0] if "." in ip else "192.168.1"
            subnet = f"{prefix}.0/24"

            cluster_domain = get_manifest_cluster_domain()
            node_obj = {
                "hostname": hname,
                "fqdn": node_data.get("fqdn", f"{hname}.{cluster_domain}"),
                "primary_ip": ip,
                "subnet_cidr": node_data.get("subnet_cidr", subnet),
                "node_category": node_data.get("node_category", traits["node_category"]),
                "always_online": node_data.get("always_online", traits.get("always_online", True)),
                "is_immutable": node_data.get("is_immutable", traits["is_immutable"]),
                "appliance_type": node_data.get("appliance_type", traits["appliance_type"]),
                "key_profile": node_data.get("key_profile", traits["key_profile"]),
                "os_family": node_data.get("os_family", traits["os_family"]),
                "distribution": node_data.get("distribution", traits["distribution"]),
                "capabilities": {
                    "has_docker": bool(has_docker),
                    "has_python": bool(node_data.get("capabilities", {}).get("has_python", not traits["is_immutable"] or traits["node_category"] in ("server", "dev")))
                }
            }

            nodes.append(node_obj)
            seen.add(hname)
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to parse {nf}: {e}\n")

    return nodes

def classify_nodes(nodes):
    """
    對節點進行多維預分類：
    1. Distro groups: 僅包含 node_category == 'server' 之可變伺服器 (隔離韌體與 hypervisors)
    2. Subnet groups: 依網路拓撲分組 (service_lan, wg_lan, openlab_mesh, etc.)
    3. Capability groups: 依運行能力分組 (docker_hosts, gateways)
    4. Appliances: 依設備類別分組 (storage, hypervisors, etc.)
    5. Endpoints: 工作站端點
    """
    classified = {
        "all_hosts": {},
        "distros": {},
        "subnets": {},
        "capabilities": {
            "docker_hosts": [],
            "gateways": []
        },
        "dev": [],
        "servers": [],
        "desktops": [],
        "appliances": {
            
            "hypervisors": []
        },
        "endpoints": []
    }

    for n in nodes:
        name = n["hostname"]
        ip = n.get("primary_ip", "")
        if not ip:
            continue
            
        classified["all_hosts"][name] = ip

        cat = n.get("node_category", "server")
        app_t = n.get("appliance_type", "none")

        if cat == "dev":
            classified["dev"].append(name)
            os_f = n.get("os_family", "Linux").lower()
            grp = "archlinux" if "arch" in os_f else "debian"
            if grp not in classified["distros"]:
                classified["distros"][grp] = []
            if name not in classified["distros"][grp]:
                classified["distros"][grp].append(name)

        elif cat in ("desktop", "endpoint"):
            classified["desktops"].append(name)
            classified["endpoints"].append(name)

        elif cat == "server":
            classified["servers"].append(name)
            os_f = n.get("os_family", "Linux").lower()
            if "photon" in os_f:
                grp = "photonos"
            elif "linux_bsd" in os_f:
                grp = "linux_bsd"
            elif "arch" in os_f:
                grp = "archlinux"
            elif "debian" in os_f or "ubuntu" in os_f:
                grp = "debian"
            elif "oracle" in os_f or "redhat" in os_f or "rhel" in os_f or "rocky" in os_f:
                grp = "rhel"
            elif "alpine" in os_f:
                grp = "alpine"
            elif "suse" in os_f:
                grp = "suse"
            else:
                grp = "linux_other"

            if grp not in classified["distros"]:
                classified["distros"][grp] = []
            classified["distros"][grp].append(name)

        # 2. Subnet 分類 (全體節點拓撲對齊)
        sub_cidr = n.get("subnet_cidr", "")
        dyn_subnets = load_manifest_networks()
        sub_alias = dyn_subnets.get(sub_cidr) or KNOWN_SUBNETS.get(sub_cidr)
        if not sub_alias and sub_cidr:
            clean_sub = sub_cidr.split("/")[0].replace(".", "_")
            sub_alias = f"subnet_{clean_sub}"
        elif not sub_alias:
            sub_alias = "unknown_net"

        if sub_alias not in classified["subnets"]:
            classified["subnets"][sub_alias] = []
        classified["subnets"][sub_alias].append(name)

        # 3. Capabilities 分類
        caps = n.get("capabilities", {})
        if caps.get("has_docker"):
            classified["capabilities"]["docker_hosts"].append(name)
        if ".254" in ip or n.get("hostname") == "gateway" or caps.get("is_gateway"):
            classified["capabilities"]["gateways"].append(name)

    return classified

def render_hosts_yaml(classified):
    """產出符合 Ansible 規範之標準 hosts.yml"""
    lines = [
        "---",
        "# ==============================================================================",
        "# Ansible Inventory: hosts.yml",
        f"# Auto-generated by OpenLabOps Classifier Engine",
        "# Pre-classification: Distros, Subnets, and Capability Groups",
        "# Strict Appliance & Immutable Hypervisor Isolation Applied",
        "# ==============================================================================",
        "all:",
        "  hosts:"
    ]

    # 全體獨立主機映射
    for name, ip in sorted(classified["all_hosts"].items()):
        lines.append(f"    {name}:")
        lines.append(f"      ansible_host: {ip}")
        if name == "localhost" or ip == "127.0.0.1":
            lines.append("      ansible_connection: local")

    lines.append("")
    lines.append("  children:")

    # 1. Distros (僅限常態伺服器)
    lines.append("    # ==========================================================================")
    lines.append("    # 1. 作業系統分類群組 (僅限常態伺服器 servers，隔離嵌入式與 Hypervisors)")
    lines.append("    # ==========================================================================")
    lines.append("    distros:")
    lines.append("      children:")
    for grp, hlist in sorted(classified["distros"].items()):
        lines.append(f"        {grp}:")
        lines.append("          hosts:")
        for h in sorted(hlist):
            lines.append(f"            {h}:")

    # 2. Subnets
    lines.append("")
    lines.append("    # ==========================================================================")
    lines.append("    # 2. 網路拓撲與服務網段群組 (Subnet & Network Groups)")
    lines.append("    # ==========================================================================")
    lines.append("    subnets:")
    lines.append("      children:")
    for grp, hlist in sorted(classified["subnets"].items()):
        lines.append(f"        {grp}:")
        lines.append("          hosts:")
        for h in sorted(hlist):
            lines.append(f"            {h}:")

    # 3. Capabilities
    lines.append("")
    lines.append("    # ==========================================================================")
    lines.append("    # 3. 節點運行能力群組 (Capability Groups: docker, gateways)")
    lines.append("    # ==========================================================================")
    lines.append("    capabilities:")
    lines.append("      children:")
    for grp, hlist in sorted(classified["capabilities"].items()):
        if hlist:
            lines.append(f"        {grp}:")
            lines.append("          hosts:")
            for h in sorted(hlist):
                lines.append(f"            {h}:")

    # 4. 相容性群組 (Role & Appliance Compatibility Groups)
    lines.append("")
    lines.append("    # ==========================================================================")
    lines.append("    # 4. 角色與設備相容群組 (Role & Appliance Compatibility Groups)")
    lines.append("    # ==========================================================================")
    if classified["dev"]:
        lines.append("    dev:")
        lines.append("      hosts:")
        for h in sorted(classified["dev"]):
            lines.append(f"        {h}:")

    lines.append("    servers:")
    lines.append("      children:")
    lines.append("        distros:")

    lines.append("    appliances:")
    lines.append("      children:")
    for app_grp, hlist in sorted(classified["appliances"].items()):
        if hlist:
            lines.append(f"        {app_grp}:")
            lines.append("          hosts:")
            for h in sorted(hlist):
                lines.append(f"            {h}:")

    if classified["desktops"]:
        lines.append("    desktops:")
        lines.append("      hosts:")
        for h in sorted(classified["desktops"]):
            lines.append(f"        {h}:")

    if classified["endpoints"]:
        lines.append("    endpoints:")
        lines.append("      children:")
        if classified["desktops"]:
            lines.append("        desktops:")
        else:
            lines.append("      hosts:")
            for h in sorted(classified["endpoints"]):
                lines.append(f"        {h}:")

    lines.append("")
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description="OpenLabOps Classifier Engine")
    parser.add_argument("--diff", action="store_true", help="Compare generated hosts.yml with existing")
    parser.add_argument("--apply", action="store_true", help="Write snapshot and hosts.yml")
    parser.add_argument("--sync-tools", action="store_true", help="Sync snapshot to /usr/local/bin/openlab/conf/")
    args = parser.parse_args()

    nodes = load_node_files(write_back=args.apply)
    if not nodes:
        print("[!] No node JSON files found in conf/nodes/. Setting empty cluster baseline.")
        if args.apply:
            CURRENT_SNAPSHOT_FILE.write_text("[]\n", encoding="utf-8")
            tools_conf = OPS_DIR / "tools" / "conf" / "current.json"
            try:
                tools_conf.parent.mkdir(parents=True, exist_ok=True)
                tools_conf.write_text("[]\n", encoding="utf-8")
            except Exception:
                pass
            if INSTALLED_TOOLS_CONF_DIR.exists():
                try:
                    (INSTALLED_TOOLS_CONF_DIR / "current.json").write_text("[]\n", encoding="utf-8")
                except Exception:
                    pass
            empty_inv = "---\nall:\n  hosts: {}\n  children:\n    servers:\n      hosts: {}\n"
            DEFAULT_HOSTS_OUT.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_HOSTS_OUT.write_text(empty_inv, encoding="utf-8")
            print("[✓] Written empty snapshot [] and clean inventory baseline.")
        sys.exit(0)

    print("=" * 65)
    print("  OpenLabOps / OpenLabOps Classifier & Ingestion Engine")
    print(f"  Loaded Nodes Count: {len(nodes)}")
    print("=" * 65)

    classified = classify_nodes(nodes)
    rendered_hosts = render_hosts_yaml(classified)

    # 1. 產生快照 current.json 內容
    snapshot_json = json.dumps(nodes, indent=2, ensure_ascii=False) + "\n"

    # 2. 比對或寫入 hosts.yml
    if DEFAULT_HOSTS_OUT.exists():
        existing_hosts = DEFAULT_HOSTS_OUT.read_text(encoding="utf-8")
        diff = list(difflib.unified_diff(
            existing_hosts.splitlines(keepends=True),
            rendered_hosts.splitlines(keepends=True),
            fromfile=f"current: {DEFAULT_HOSTS_OUT.name}",
            tofile="classified: hosts.yml",
            n=2
        ))
        if diff:
            print("\n[+] Diff detected against current hosts.yml:")
            for l in diff[:35]:
                if l.startswith("+"):
                    sys.stdout.write(f"\033[32m{l}\033[0m")
                elif l.startswith("-"):
                    sys.stdout.write(f"\033[31m{l}\033[0m")
                else:
                    sys.stdout.write(l)
            if len(diff) > 35:
                print(f"  ... ({len(diff)-35} more lines)")
        else:
            print("\n[✓] Generated hosts.yml is 100% IDENTICAL to current baseline.")
    else:
        print(f"\n[+] New hosts.yml will be created at {DEFAULT_HOSTS_OUT}")

    if args.apply:
        # 寫入 snapshot
        CURRENT_SNAPSHOT_FILE.write_text(snapshot_json, encoding="utf-8")
        print(f"\n[✓] Written current snapshot: {CURRENT_SNAPSHOT_FILE}")

        # 寫入 hosts.yml
        DEFAULT_HOSTS_OUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_HOSTS_OUT.write_text(rendered_hosts, encoding="utf-8")
        print(f"[✓] Written pre-classified inventory: {DEFAULT_HOSTS_OUT}")
        # 同步至 ansible / inventory / hosts.yml
        ans_mirror = OPS_DIR / "ansible" / "inventory" / "hosts.yml"
        ans_mirror.parent.mkdir(parents=True, exist_ok=True)
        ans_mirror.write_text(rendered_hosts, encoding="utf-8")

        # 發布至工具鏈端
        tools_conf = OPS_DIR / "tools" / "conf" / "current.json"
        try:
            tools_conf.parent.mkdir(parents=True, exist_ok=True)
            tools_conf.write_text(snapshot_json, encoding="utf-8")
        except Exception:
            pass

        if args.sync_tools or INSTALLED_TOOLS_CONF_DIR.exists():
            try:
                INSTALLED_TOOLS_CONF_DIR.mkdir(parents=True, exist_ok=True)
                target_installed_conf = INSTALLED_TOOLS_CONF_DIR / "current.json"
                target_installed_conf.write_text(snapshot_json, encoding="utf-8")
                print(f"[✓] Synced snapshot to tools suite: {target_installed_conf}")
            except (PermissionError, OSError) as e:
                print(f"[!] Note: Sudo / write access required to write to {INSTALLED_TOOLS_CONF_DIR}/current.json ({e})")

    print("\n" + "=" * 65)
    if not args.apply:
        print("[!] Dry-run complete. Run with --apply to write changes.")

if __name__ == "__main__":
    main()
