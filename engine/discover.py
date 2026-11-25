#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# OpenLabOps / OpenLabOps Dynamic Machine Telemetry Discovery Engine
# File: engine/discover.py
# Governed by [INV-01] (Zero External Dependencies) & [INV-04] (Ground Truth)
# ==============================================================================

import sys
import os
import re
import json
import shlex
import socket
import subprocess
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_NAME = REPO_ROOT.name
_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

# Determine default output directory (node-information/, NEVER conf/nodes/)
CONFIGS_OUT_DIR = REPO_ROOT / "node-information"
if (REPO_ROOT.parent / f"{PROJECT_NAME[:7]}-configs").exists():
    CONFIGS_OUT_DIR = REPO_ROOT.parent / f"{PROJECT_NAME[:7]}-configs" / "node-information"
elif (REPO_ROOT.parent / "openlab-configs").exists():
    CONFIGS_OUT_DIR = REPO_ROOT.parent / "openlab-configs" / "node-information"
elif (REPO_ROOT.parent / "openlab-configs").exists():
    CONFIGS_OUT_DIR = REPO_ROOT.parent / "openlab-configs" / "node-information"

# Inline lightweight pure standard-library audit probe (Runs on target node)
INLINE_AUDIT_PROBE = r"""
import os, sys, json, socket, subprocess

def run_cmd(c):
    try:
        return subprocess.run(c, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""

hostname = socket.gethostname()
os_name = ""
if os.path.exists("/etc/os-release"):
    with open("/etc/os-release") as f:
        for line in f:
            if line.startswith("PRETTY_NAME="):
                os_name = line.strip().split("=", 1)[1].strip('"\'')
                break
if not os_name:
    os_name = run_cmd("uname -s -r")

cores = os.cpu_count() or 1
cpu_model = "Unknown"
if os.path.exists("/proc/cpuinfo"):
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                cpu_model = line.split(":", 1)[1].strip()
                break

mem_total_mb = 0
mem_free_mb = 0
if os.path.exists("/proc/meminfo"):
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                k = parts[0].strip()
                v = parts[1].strip().split()[0]
                if k == "MemTotal": mem_total_mb = int(v) // 1024
                elif k == "MemAvailable": mem_free_mb = int(v) // 1024

disks = []
df_out = run_cmd("df -hP -x tmpfs -x devtmpfs 2>/dev/null")
for line in df_out.splitlines()[1:]:
    p = line.split()
    if len(p) >= 6:
        disks.append({"fs": p[0], "size": p[1], "used": p[2], "avail": p[3], "pct": p[4], "mount": p[5]})

containers = []
docker_ps = run_cmd("docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null")
for line in docker_ps.splitlines():
    p = line.split("|")
    if len(p) >= 3:
        containers.append({"name": p[0], "image": p[1], "status": p[2], "ports": p[3] if len(p) > 3 else ""})

auth_keys = []
auth_path = os.path.expanduser("~/.ssh/authorized_keys")
if os.path.exists(auth_path):
    with open(auth_path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                auth_keys.append({"options": parts[0] if parts[0].startswith("from=") else "", "type": parts[1] if parts[0].startswith("from=") else parts[0]})

print(json.dumps({
    "hostname": hostname,
    "os": os_name,
    "system": {
        "cpu": {"model": cpu_model, "cores": cores},
        "memory": {"total_mb": mem_total_mb, "free_mb": mem_free_mb}
    },
    "storage": disks,
    "docker": {"containers": containers},
    "authorized_keys": auth_keys
}))
"""

def load_manifest_hosts(manifest_override=None):
    # 1. 若未強制指定 --manifest，優先從實機已納管之 conf/nodes/*.json (或 current.json) 載入真實節點 [INV-04]
    if not manifest_override:
        nodes_dir = REPO_ROOT / "conf" / "nodes"
        probed_hosts = []
        seen = set()
        if nodes_dir.exists():
            for nf in sorted(nodes_dir.glob("*.json")):
                if nf.name in ("current.json", "archive") or nf.name.startswith("."):
                    continue
                try:
                    nd = json.loads(nf.read_text(encoding="utf-8"))
                    hname = nd.get("hostname") or nf.stem
                    hip = nd.get("primary_ip") or nd.get("ansible_host")
                    if hname and hip and hname not in seen:
                        probed_hosts.append({"name": str(hname), "ip": str(hip)})
                        seen.add(hname)
                except Exception:
                    pass
            if not probed_hosts and (nodes_dir / "current.json").exists():
                try:
                    snap = json.loads((nodes_dir / "current.json").read_text(encoding="utf-8"))
                    if isinstance(snap, list):
                        for nd in snap:
                            hname = nd.get("hostname")
                            hip = nd.get("primary_ip") or nd.get("ansible_host")
                            if hname and hip and hname not in seen:
                                probed_hosts.append({"name": str(hname), "ip": str(hip)})
                                seen.add(hname)
                except Exception:
                    pass
        if probed_hosts:
            return probed_hosts

    # 2. 備援：僅於強制指定 --manifest 或尚無任何已探測節點時，才參考 *.manifest.yml
    manifest_path = manifest_override
    if not manifest_path:
        for cand in [REPO_ROOT / "conf" / "openlab.manifest.yml", REPO_ROOT / "conf" / "openlab.manifest.yml", REPO_ROOT / "tests" / "conf" / "openlab.manifest.test.yml"]:
            if cand.exists():
                manifest_path = cand
                break
    if not manifest_path or not Path(manifest_path).exists():
        return []

    lib_dir = str(REPO_ROOT / "tools" / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata

    data = parse_yaml_file(manifest_path)
    hosts = []
    if isinstance(data.get("targets"), list):
        for t in data["targets"]:
            if isinstance(t, dict) and t.get("name") and t.get("ip"):
                hosts.append({"name": str(t["name"]), "ip": str(t["ip"])})
    meta_map = extract_manifest_hosts_metadata(data)
    for hname, hmeta in meta_map.items():
        hosts.append({"name": hname, "ip": hmeta["ip"]})
    return hosts

def probe_local(dest_file):
    try:
        res = subprocess.run([sys.executable, "-c", INLINE_AUDIT_PROBE], capture_output=True, text=True, check=True)
        if res.stdout.strip().startswith("{"):
            parsed = json.loads(res.stdout)
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            return True
    except Exception:
        pass
    return False

def probe_remote(h, dest_file):
    ip = h["ip"]
    user = h.get("user") or ("lab" if (Path.home() / ".ssh" / "ansible.key").exists() else "ansible")
    key_cand = Path.home() / ".ssh" / f"{user}.key"
    remote_cmd = f"python3 -c {shlex.quote(INLINE_AUDIT_PROBE)} 2>/dev/null"
    cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=3",
        "-o", "StrictHostKeyChecking=accept-new",
    ]
    if key_cand.exists():
        cmd.extend(["-i", str(key_cand)])
    cmd.extend([f"{user}@{ip}", remote_cmd])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        if res.returncode == 0 and res.stdout.strip().startswith("{"):
            parsed = json.loads(res.stdout)
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            return True
    except Exception:
        pass
    return False

def _get_engine_version() -> str:
    ver_file = Path(__file__).resolve().parent.parent / "VERSION"
    if ver_file.exists():
        return ver_file.read_text(encoding="utf-8").strip() or "1.0.0"
    return "1.0.0"

def main():
    parser = argparse.ArgumentParser(prog="lab-discover", description="Dynamic Node Discovery & Fact Harvester")
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Dynamic Discovery (lab-discover) v{_get_engine_version()}")
    parser.add_argument("--out-dir", default=str(CONFIGS_OUT_DIR), help="Output directory for node-information JSONs")
    parser.add_argument("--node", help="Probe a specific node only")
    parser.add_argument("--manifest", help="Manifest path to read targets from")
    args = parser.parse_args()

    out_path = Path(args.out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    hosts = load_manifest_hosts(args.manifest)
    print("=" * 68)
    print(f"  [{PROJECT_NAME}] Dynamic Telemetry Fact Harvester (Found {len(hosts)} declared nodes)")
    print(f"  Target Output: {out_path}")
    print("=" * 68)

    my_hostname = socket.gethostname().split(".")[0]

    for h in hosts:
        name = str(h["name"])
        ip = str(h["ip"])
        if not _SAFE_HOST_RE.match(name) or ".." in name:
            continue
        if args.node and args.node != name:
            continue

        print(f"[*] Probing {name:<14} ({ip:<15})... ", end="", flush=True)
        dest = out_path / f"node_{name}.json"
        
        success = False
        if name.lower() == my_hostname.lower() or ip in ["127.0.0.1", "localhost"]:
            success = probe_local(dest)
        else:
            success = probe_remote(h, dest)

        if success:
            print(f"\033[32m[LIVE CAPTURED]\033[0m -> saved {dest.name}")
        else:
            if dest.exists():
                print(f"\033[33m[OFFLINE/RETAINED]\033[0m (kept cached specs)")
            else:
                print(f"\033[31m[OFFLINE/SKIPPED]\033[0m")

    print("=" * 68)
    print("[✓] Dynamic discovery finished. Telemetry facts are up to date.")

if __name__ == "__main__":
    main()
