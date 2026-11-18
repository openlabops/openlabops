#!/usr/bin/env python3
"""
OpenLabOps Node Audit Script (Linux JSON Edition)
Generates runtime hardware, network, storage, systemd & Docker container spec in JSON
"""
import os
import sys
import json
import socket
import datetime
import subprocess

def run_cmd(cmd, check=False):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.stdout.strip()
    except Exception:
        return ""

def get_os_info():
    pretty_name = ""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    pretty_name = line.strip().split("=", 1)[1].strip('"\'')
                    break
    if not pretty_name:
        pretty_name = run_cmd("uname -s")
    return pretty_name

def get_cpu_info():
    model = ""
    cores = os.cpu_count() or 1
    if os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    if not model:
        model = run_cmd("lscpu | awk -F: '/Model name/{gsub(/^[ \\t]+/, \"\", $2); print $2}' | head -n1")
    return {"model": model or "Unknown", "cores": cores}

def get_memory_info():
    mem_total_kb = 0
    mem_free_kb = 0
    mem_avail_kb = 0
    swap_total_kb = 0
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().split()[0]
                    if k == "MemTotal": mem_total_kb = int(v)
                    elif k == "MemFree": mem_free_kb = int(v)
                    elif k == "MemAvailable": mem_avail_kb = int(v)
                    elif k == "SwapTotal": swap_total_kb = int(v)

    used_kb = mem_total_kb - (mem_avail_kb or mem_free_kb)
    return {
        "total_mb": round(mem_total_kb / 1024),
        "used_mb": round(used_kb / 1024),
        "free_mb": round((mem_avail_kb or mem_free_kb) / 1024),
        "swap_total_mb": round(swap_total_kb / 1024)
    }

def get_network_interfaces():
    interfaces = []
    # 優先嘗試 ip -j addr
    ip_j = run_cmd("ip -j addr")
    if ip_j:
        try:
            data = json.loads(ip_j)
            for item in data:
                ifname = item.get("ifname", "")
                if ifname == "lo":
                    continue
                
                if_type = "實體 / VM 網卡"
                if os.path.exists(f"/sys/class/net/{ifname}/device"):
                    if_type = "實體 / VM 網卡"
                elif ifname.startswith("wg"):
                    if_type = "WireGuard 介面"
                elif ifname.startswith("macvlan") or os.path.exists(f"/sys/class/net/{ifname}/macvlan"):
                    if_type = "Host Macvlan 介面"
                elif ifname.startswith("docker") or ifname.startswith("br-") or ifname.startswith("veth"):
                    if_type = "Docker 虛擬橋接/介面"

                ips = []
                for addr in item.get("addr_info", []):
                    local = addr.get("local")
                    prefix = addr.get("prefixlen")
                    if local and prefix:
                        ips.append(f"{local}/{prefix}")

                interfaces.append({
                    "name": ifname,
                    "type": if_type,
                    "mac": item.get("address", "N/A"),
                    "mtu": item.get("mtu", 1500),
                    "operstate": item.get("operstate", "unknown"),
                    "ips": ips
                })
            return interfaces
        except Exception:
            pass

    # 備選方法：遍歷 /sys/class/net
    if os.path.exists("/sys/class/net"):
        for ifname in os.listdir("/sys/class/net"):
            if ifname == "lo":
                continue
            mac = run_cmd(f"cat /sys/class/net/{ifname}/address 2>/dev/null") or "N/A"
            mtu = run_cmd(f"cat /sys/class/net/{ifname}/mtu 2>/dev/null") or "1500"
            operstate = run_cmd(f"cat /sys/class/net/{ifname}/operstate 2>/dev/null") or "unknown"
            raw_ips = run_cmd(f"ip -o addr show dev {ifname} 2>/dev/null | awk '{{print $4}}'")
            ips = [x for x in raw_ips.split() if x]

            if_type = "實體 / VM 網卡"
            if ifname.startswith("wg"):
                if_type = "WireGuard 介面"
            elif ifname.startswith("macvlan"):
                if_type = "Host Macvlan 介面"

            interfaces.append({
                "name": ifname,
                "type": if_type,
                "mac": mac,
                "mtu": int(mtu) if mtu.isdigit() else 1500,
                "operstate": operstate,
                "ips": ips
            })
    return interfaces

def get_wireguard():
    wg_list = []
    dump = run_cmd("wg show all dump 2>/dev/null")
    if dump:
        lines = dump.splitlines()
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 5:
                wg_list.append({
                    "interface": parts[0],
                    "endpoint": parts[3] if parts[3] != "(none)" else "none",
                    "allowed_ips": parts[4]
                })
    return wg_list

def get_storage():
    storage = []
    df_raw = run_cmd("df -h -T -P 2>/dev/null")
    if df_raw:
        lines = df_raw.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 7:
                fstype = parts[1]
                if fstype in ("tmpfs", "devtmpfs", "overlay", "squashfs"):
                    continue
                storage.append({
                    "device": parts[0],
                    "fstype": fstype,
                    "total": parts[2],
                    "used": parts[3],
                    "free": parts[4],
                    "percent": parts[5],
                    "mount": parts[6]
                })
    return storage

def get_services():
    services_raw = run_cmd("systemctl list-unit-files --state=enabled --type=service 2>/dev/null | awk 'NR>1 && $1 ~ /\\.service$/ {print $1}'")
    if services_raw:
        return [s for s in services_raw.split() if s]
    return []

def get_docker_cmd():
    if not run_cmd("command -v docker 2>/dev/null"):
        return ""
    if run_cmd("docker ps >/dev/null 2>&1 && echo ok") == "ok":
        return "docker"
    if run_cmd("sudo -n docker ps >/dev/null 2>&1 && echo ok") == "ok":
        return "sudo -n docker"
    return ""

def get_docker_info():
    docker_info = {"installed": False, "networks": [], "containers": []}
    d_cmd = get_docker_cmd()
    if not d_cmd:
        return docker_info

    docker_info["installed"] = True
    # 網路資訊
    net_ids = run_cmd(f"{d_cmd} network ls -q 2>/dev/null").split()
    if net_ids:
        inspect_raw = run_cmd(f"{d_cmd} network inspect {' '.join(net_ids)} 2>/dev/null")
        if inspect_raw:
            try:
                nets = json.loads(inspect_raw)
                for net in nets:
                    subnets = []
                    gateways = []
                    for ipam in net.get("IPAM", {}).get("Config", []):
                        if "Subnet" in ipam: subnets.append(ipam["Subnet"])
                        if "Gateway" in ipam: gateways.append(ipam["Gateway"])
                    parent = net.get("Options", {}).get("parent", "")
                    docker_info["networks"].append({
                        "name": net.get("Name"),
                        "driver": net.get("Driver"),
                        "subnets": subnets,
                        "gateways": gateways,
                        "parent": parent or "N/A"
                    })
            except Exception:
                pass

    # 容器資訊
    c_ids = run_cmd(f"{d_cmd} ps -q 2>/dev/null").split()
    if c_ids:
        inspect_raw = run_cmd(f"{d_cmd} inspect {' '.join(c_ids)} 2>/dev/null")
        if inspect_raw:
            try:
                conts = json.loads(inspect_raw)
                for c in conts:
                    name = c.get("Name", "").lstrip("/")
                    img = c.get("Config", {}).get("Image", "")
                    state = c.get("State", {}).get("Status", "")
                    ports = run_cmd(f"{d_cmd} ps --filter 'id={c.get('Id')}' --format '{{{{.Ports}}}}' 2>/dev/null") or "none"
                    net_settings = []
                    for net_name, net_cfg in c.get("NetworkSettings", {}).get("Networks", {}).items():
                        net_settings.append({
                            "network": net_name,
                            "ip": net_cfg.get("IPAddress") or "Host/None",
                            "mac": net_cfg.get("MacAddress") or "N/A"
                        })
                    docker_info["containers"].append({
                        "name": name,
                        "image": img,
                        "status": state,
                        "ports": ports,
                        "networks": net_settings
                    })
            except Exception:
                pass

    return docker_info


def get_authorized_keys():
    """審計本機所有使用者帳號之 authorized_keys 檔案"""
    import glob
    import base64
    import hashlib

    entries = []
    candidates = []

    # 1. 系統使用者 home 目錄 (/home/*)
    for p in sorted(glob.glob("/home/*/.ssh/authorized_keys")):
        parts = p.split("/")
        if len(parts) >= 3:
            candidates.append((parts[2], p))

    # 2. root 使用者
    if os.path.exists("/root/.ssh/authorized_keys"):
        candidates.append(("root", "/root/.ssh/authorized_keys"))

    # 3. Virtualization (/etc/ssh/keys-root/authorized_keys)
    if os.path.exists("/etc/ssh/keys-root/authorized_keys"):
        candidates.append(("root", "/etc/ssh/keys-root/authorized_keys"))

    known_types = {
        "ssh-ed25519", "ssh-rsa", "ssh-dss",
        "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
        "sk-ssh-ed25519@openssh.com", "sk-ecdsa-sha2-nistp256@openssh.com"
    }

    for account, auth_file in candidates:
        try:
            mode = oct(os.stat(auth_file).st_mode & 0o777)
            with open(auth_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split()
                    options = ""
                    key_type = ""
                    key_b64 = ""
                    comment = ""

                    if parts[0] in known_types:
                        key_type = parts[0]
                        key_b64 = parts[1] if len(parts) > 1 else ""
                        comment = " ".join(parts[2:]) if len(parts) > 2 else ""
                    else:
                        type_idx = -1
                        for i, p in enumerate(parts):
                            if p in known_types:
                                type_idx = i
                                break
                        if type_idx != -1:
                            options = " ".join(parts[:type_idx])
                            key_type = parts[type_idx]
                            key_b64 = parts[type_idx + 1] if len(parts) > type_idx + 1 else ""
                            comment = " ".join(parts[type_idx + 2:]) if len(parts) > type_idx + 2 else ""
                        else:
                            key_type = "unknown"
                            comment = line

                    fingerprint = ""
                    if key_b64:
                        try:
                            raw = base64.b64decode(key_b64)
                            fp_hash = hashlib.sha256(raw).digest()
                            fingerprint = "SHA256:" + base64.b64encode(fp_hash).decode("ascii").rstrip("=")
                        except Exception:
                            pass

                    entries.append({
                        "account": account,
                        "file": auth_file,
                        "file_mode": mode,
                        "line_num": line_idx,
                        "options": options,
                        "key_type": key_type,
                        "key_b64": key_b64,
                        "comment": comment,
                        "fingerprint": fingerprint
                    })
        except Exception:
            continue

    return entries


def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else f"/tmp/node_{socket.gethostname()}.json"
    hostname = socket.gethostname()

    default_gw = run_cmd("ip route show default 2>/dev/null | awk '{print $3 \" dev \" $5}'")

    data = {
        "node_type": "linux",
        "hostname": hostname,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "system": {
            "os": get_os_info(),
            "kernel": run_cmd("uname -r"),
            "cpu": get_cpu_info(),
            "memory": get_memory_info(),
            "default_gateway": default_gw or "none"
        },
        "network_interfaces": get_network_interfaces(),
        "wireguard": get_wireguard(),
        "storage": get_storage(),
        "services": get_services(),
        "docker": get_docker_info(),
        "authorized_keys": get_authorized_keys()
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Node audit JSON generated at: {output_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
