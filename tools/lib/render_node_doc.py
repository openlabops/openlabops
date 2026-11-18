#!/usr/bin/env python3
"""
OpenLabOps Node & Network Document Renderer
Converts machine-readable JSON node/topology specs into human-readable Markdown
"""

import os
import sys
import json
import argparse
from typing import Dict, Any

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

try:
    from core.ui_theme import ui_info, ui_success, ui_warn, ui_error
except ImportError:
    def ui_info(m): print(f"[*] {m}")
    def ui_success(m): print(f"[+] {m}")
    def ui_warn(m): print(f"[!] {m}")
    def ui_error(m): print(f"[-] {m}")


def render_linux_doc(data: Dict[str, Any]) -> str:
    h = data.get("hostname", "Unknown")
    gen_date = data.get("generated_at", "")
    sys_info = data.get("system", {})
    cpu = sys_info.get("cpu", {})
    mem = sys_info.get("memory", {})

    lines = [
        "---",
        f'title: "節點手冊: {h}"',
        f'date: "{gen_date}"',
        "tags:",
        "  - homelab",
        "  - node-spec",
        "---",
        "",
        f"# 節點手冊：{h}",
        "",
        f"> 產生時間：`{gen_date}`",
        "",
        "**硬體與系統規格**",
        "",
        "| 項目 | 規格值 |",
        "| :--- | :--- |",
        f"| **主機名稱** | `{h}` |",
        f"| **作業系統** | `{sys_info.get('os', 'Linux')}` |",
        f"| **核心版本** | `{sys_info.get('kernel', 'N/A')}` |",
        f"| **CPU 型號** | {cpu.get('model', 'Unknown')} |",
        f"| **vCPU 核心數** | `{cpu.get('cores', 1)}` |",
        f"| **記憶體 (已用 / 總量)** | `{mem.get('used_mb', 0)} MB / {mem.get('total_mb', 0)} MB` (Swap: `{mem.get('swap_total_mb', 0)} MB`) |",
        f"| **預設閘道 (Default Gateway)** | `{sys_info.get('default_gateway', 'None')}` |",
        "",
        "**核心網路介面 (實體 / VM 網卡 / WireGuard / Macvlan)**",
        "",
        "| 介面名稱 | 類型 | 實際 IP (IPv4 / IPv6) | MAC 位址 | MTU | 狀態 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for iface in data.get("network_interfaces", []):
        ips = "<br>".join([f"`{ip}`" for ip in iface.get("ips", [])]) or "*未配發 IP*"
        lines.append(f"| `{iface.get('name')}` | {iface.get('type')} | {ips} | `{iface.get('mac')}` | `{iface.get('mtu')}` | `{iface.get('operstate')}` |")

    wg_list = data.get("wireguard", [])
    if wg_list:
        lines.extend([
            "",
            "**WireGuard Mesh 運作狀態 (wg show)**",
            "",
            "| 介面名稱 | 允許連線 IP (Allowed IPs) | 端點 (Endpoint) |",
            "| :--- | :--- | :--- |"
        ])
        for wg in wg_list:
            lines.append(f"| `{wg.get('interface')}` | `{wg.get('allowed_ips')}` | `{wg.get('endpoint')}` |")

    storage_list = data.get("storage", [])
    if storage_list:
        lines.extend([
            "",
            "**儲存與磁碟掛載**",
            "",
            "| 掛載點 | 來源裝置 / 網路路徑 | 檔案系統 | 容量 (已用 / 總量) | 使用率 |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])
        for s in storage_list:
            lines.append(f"| `{s.get('mount')}` | `{s.get('device')}` | `{s.get('fstype')}` | {s.get('used')} / {s.get('total')} | {s.get('percent')} |")

    services = data.get("services", [])
    lines.extend([
        "",
        "**已啟用系統服務 (All Enabled Systemd Services)**",
        ""
    ])
    if services:
        for s in services:
            lines.append(f"* `{s}`")
    else:
        lines.append("* 無啟用中的服務")

    docker_info = data.get("docker", {})
    if docker_info.get("installed"):
        lines.extend([
            "",
            "**Docker 網路定義清單 (含 Driver 與 Subnet)**",
            "",
            "| 網路名稱 (Network) | 驅動 (Driver) | 網段 (Subnet) | 閘道 (Gateway) | 父介面 (Parent Iface) |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])
        for net in docker_info.get("networks", []):
            subnets = ", ".join(net.get("subnets", [])) or "None"
            gws = ", ".join(net.get("gateways", [])) or "None"
            lines.append(f"| **{net.get('name')}** | `{net.get('driver')}` | `{subnets}` | `{gws}` | `{net.get('parent')}` |")

        lines.extend([
            "",
            "**Docker 容器實體與網路拓撲 (含各網路實際 IP 與 Macvlan)**",
            "",
            "| 容器名稱 | 映像檔 | 運行狀態 | 埠號對應 (Port Mappings) | 網路與實際 IP (含 MAC 位址) |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])
        for c in docker_info.get("containers", []):
            nets = "<br>".join([f"[`{n.get('network')}`] {n.get('ip')} (MAC: {n.get('mac')})" for n in c.get("networks", [])])
            lines.append(f"| **{c.get('name')}** | `{c.get('image')}` | {c.get('status')} | `{c.get('ports')}` | {nets} |")
    else:
        lines.extend([
            "",
            "**Docker 服務狀態**",
            "",
            "* 本節點未安裝 Docker 或未運行 Docker Daemon。"
        ])

    lines.append("\n---\n*Human View Rendered from Machine JSON.*")
    return "\n".join(lines)


def render_file(json_path: str) -> str:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return render_linux_doc(data)


def main():
    from core.version import get_local_version
    parser = argparse.ArgumentParser(prog="render-node-doc", description="Render Machine JSON node specs into Markdown")
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Node Doc Renderer (render-node-doc) v{get_local_version()}")
    parser.add_argument("input_path", help="Path to a JSON file or directory containing JSON files")
    parser.add_argument("--output", "-o", help="Target output Markdown file (for single file mode)")
    parser.add_argument("--out-dir", "-d", help="Target output directory (for batch mode)")

    args = parser.parse_args()

    if os.path.isfile(args.input_path):
        md = render_file(args.input_path)
        if args.output:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(md + "\n")
            ui_success(f"手冊已渲染至: {args.output}")
        else:
            print(md)
    elif os.path.isdir(args.input_path):
        target_dir = args.out_dir or args.input_path
        os.makedirs(target_dir, exist_ok=True)
        count = 0
        for fname in sorted(os.listdir(args.input_path)):
            if fname.endswith(".json"):
                if fname.startswith("packages_"):
                    continue
                fpath = os.path.join(args.input_path, fname)
                md = render_file(fpath)
                if fname.startswith("node_"):
                    out_name = "Node_" + fname[5:-5] + ".md"
                else:
                    out_name = "Node_" + fname[:-5] + ".md"
                out_fpath = os.path.join(target_dir, out_name)
                with open(out_fpath, "w", encoding="utf-8") as f:
                    f.write(md + "\n")
                ui_info(f"已轉出: {out_fpath}")
                count += 1
        ui_success(f"批次轉出完成，共渲染 {count} 個節點手冊至 {target_dir}")
    else:
        ui_error(f"路徑不存在: {args.input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
