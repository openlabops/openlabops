#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Live Cluster Probe Engine (Zero-Cache Real-Time Telemetry)
並行活體探測全網節點之 authorized_keys (含各帳號與 Comment) 與系統套件即時待更新狀態。
"""

import os
import sys
import time
import json
import shlex
import base64
import hashlib
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from core.config import get_cluster_targets
CLUSTER_TARGETS = get_cluster_targets()

REMOTE_PYTHON_PROBE = r'''
import os, glob, hashlib, base64, json, subprocess

candidates = []
for p in sorted(glob.glob("/home/*/.ssh/authorized_keys") + glob.glob("/root/.ssh/authorized_keys") + glob.glob("/etc/ssh/keys-root/authorized_keys") + glob.glob("/cf/conf/authorized_keys")):
    parts = p.split("/")
    acc = "root"
    if "/home/" in p:
        idx = parts.index("home")
        if len(parts) > idx + 1: acc = parts[idx+1]
    candidates.append((acc, p))

known_types = {"ssh-ed25519", "ssh-rsa", "ssh-dss", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"}
keys = []
for acc, fpath in candidates:
    raw_lines = []
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = f.readlines()
    except Exception:
        try:
            r = subprocess.run(["sudo", "cat", str(fpath)], capture_output=True, text=True)
            if r.returncode == 0:
                raw_lines = r.stdout.splitlines()
        except Exception:
            pass
    if not raw_lines: continue
    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        try:
            parts = line.split()
            opts, ktype, b64, comment = "", "", "", ""
            if parts[0] in known_types:
                ktype = parts[0]
                b64 = parts[1] if len(parts) > 1 else ""
                comment = " ".join(parts[2:]) if len(parts) > 2 else ""
            else:
                for i, p in enumerate(parts):
                    if p in known_types:
                        opts = " ".join(parts[:i])
                        ktype = p
                        b64 = parts[i+1] if len(parts) > i+1 else ""
                        comment = " ".join(parts[i+2:]) if len(parts) > i+2 else ""
                        break
            fp = ""
            if b64:
                try: fp = "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(b64)).digest()).decode("ascii").rstrip("=")
                except: pass
            keys.append({"account": acc, "options": opts or "(無 IP 限制)", "key_type": ktype, "comment": comment, "fingerprint": fp, "b64": b64})
        except: pass

upg_count = 0
upg_samples = []
try:
    if os.path.exists("/usr/bin/pacman") or os.path.exists("/bin/pacman"):
        res = subprocess.run("pacman -Qu 2>/dev/null", shell=True, capture_output=True, text=True)
        lines = [l.split()[0] for l in res.stdout.strip().split("\n") if l.strip()]
        upg_count = len(lines)
        upg_samples = lines[:3]
    elif os.path.exists("/usr/bin/tdnf"):
        res = subprocess.run("sudo tdnf check-update 2>/dev/null", shell=True, capture_output=True, text=True)
        lines = [l.split()[0] for l in res.stdout.strip().split("\n") if l.strip() and not l.startswith("Loading") and not l.startswith("Refreshing")]
        upg_count = len(lines)
        upg_samples = lines[:3]
    elif os.path.exists("/usr/bin/dnf"):
        res = subprocess.run("sudo dnf check-update 2>/dev/null", shell=True, capture_output=True, text=True)
        lines = [l.split()[0] for l in res.stdout.strip().split("\n") if any(l.endswith(arch) for arch in [".aarch64", ".noarch", ".x86_64", "ol10_appstream", "ol10_baseos_latest"])]
        upg_count = len(lines)
        upg_samples = [l.split(".")[0] for l in lines[:3]]
    elif os.path.exists("/sbin/apk") or os.path.exists("/usr/bin/apk"):
        res = subprocess.run("apk version -v -l '<' 2>/dev/null", shell=True, capture_output=True, text=True)
        lines = [l.split()[0] for l in res.stdout.strip().split("\n") if l.strip() and "<" in l]
        upg_count = len(lines)
        upg_samples = lines[:3]
    elif os.path.exists("/usr/bin/apt-get") or os.path.exists("/usr/bin/apt"):
        res = subprocess.run("apt-get -s upgrade 2>/dev/null", shell=True, capture_output=True, text=True)
        lines = [l.split()[1] for l in res.stdout.strip().split("\n") if l.startswith("Inst ")]
        upg_count = len(lines)
        upg_samples = lines[:3]
    elif os.path.exists("/usr/sbin/pkg"):
        res = subprocess.run("pkg upgrade -n 2>/dev/null", shell=True, capture_output=True, text=True)
        for line in res.stdout.split("\n"):
            if "to be upgraded" in line:
                for w in line.split():
                    if w.isdigit(): upg_count = int(w); break
            if "->" in line:
                pkg_name = line.split(":")[0].strip()
                if pkg_name and len(upg_samples) < 3: upg_samples.append(pkg_name)
        pass
except: pass

reboot_required = False
reboot_reason = ""
try:
    if os.path.exists("/var/run/reboot-required") or os.path.exists("/run/reboot-required"):
        reboot_required = True
        reboot_reason = "flag_file"
    elif os.path.exists("/etc/arch-release"):
        running_k = os.uname().release
        if not os.path.exists(f"/usr/lib/modules/{running_k}"):
            reboot_required = True
            reboot_reason = "kernel_replaced"
    elif os.path.exists("/usr/bin/needs-restarting"):
        res = subprocess.run("sudo needs-restarting -r", shell=True, capture_output=True)
        if res.returncode == 1:
            reboot_required = True
            reboot_reason = "core_libraries"
    elif os.path.exists("/usr/bin/tdnf"):
        res = subprocess.run("rpm -q --last linux-esx linux 2>/dev/null | grep -E '^linux' | head -n 1", shell=True, capture_output=True, text=True)
        if res.stdout:
            pkg_name = res.stdout.split()[0]
            pkg_ver = pkg_name.rsplit(".", 1)[0]
            if pkg_ver.startswith("linux-esx-"): pkg_ver = pkg_ver[len("linux-esx-"):]
            elif pkg_ver.startswith("linux-"): pkg_ver = pkg_ver[len("linux-"):]
            running_ver = os.uname().release
            if running_ver.endswith("-esx"): running_ver = running_ver[:-len("-esx")]
            if pkg_ver and running_ver and pkg_ver != running_ver:
                reboot_required = True
                reboot_reason = "kernel_updated"
except: pass

print(json.dumps({"keys": keys, "upg_count": upg_count, "upg_samples": upg_samples, "reboot_required": reboot_required, "reboot_reason": reboot_reason}))
'''


REMOTE_POSIX_SH_PROBE = r'''
keys_json=""
for f in /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys /etc/ssh/keys-root/authorized_keys /cf/conf/authorized_keys; do
    [ -f "$f" ] || continue
    acc="root"
    case "$f" in
        /home/*)
            acc=$(echo "$f" | awk -F/ '{print $3}')
            ;;
    esac
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ""|\#*) continue ;;
        esac
        first=$(echo "$line" | awk '{print $1}')
        case "$first" in
            ssh-*|ecdsa-*)
                opts=""
                ktype=$first
                b64=$(echo "$line" | awk '{print $2}')
                comment=$(echo "$line" | awk '{$1=""; $2=""; sub(/^  */, ""); print}')
                ;;
            *)
                opts=$first
                ktype=$(echo "$line" | awk '{print $2}')
                b64=$(echo "$line" | awk '{print $3}')
                comment=$(echo "$line" | awk '{$1=""; $2=""; $3=""; sub(/^  */, ""); print}')
                ;;
        esac
        fp=""
        if [ -n "$b64" ]; then
            raw_fp=$(printf "%s" "$b64" | openssl base64 -d -A 2>/dev/null | openssl dgst -sha256 -binary 2>/dev/null | openssl base64 2>/dev/null | tr -d "\n" | sed 's/=*$//')
            if [ -n "$raw_fp" ]; then fp="SHA256:$raw_fp"; fi
        fi
        opts_disp="${opts:-(無 IP 限制)}"
        opts_esc=$(echo "$opts_disp" | sed 's/"/\\"/g')
        comment_esc=$(echo "$comment" | sed 's/"/\\"/g')
        item="{\"account\":\"$acc\",\"options\":\"$opts_esc\",\"key_type\":\"$ktype\",\"comment\":\"$comment_esc\",\"fingerprint\":\"$fp\",\"b64\":\"$b64\"}"
        if [ -n "$keys_json" ]; then keys_json="$keys_json,$item"; else keys_json="$item"; fi
    done < "$f"
done

upg_count=0
upg_samples=""
if [ -x /usr/sbin/pkg ]; then
    out=$(pkg upgrade -n 2>/dev/null)
    cnt=$(echo "$out" | grep -i "to be upgraded" | awk '{for(i=1;i<=NF;i++) if($i~/^[0-9]+$/) {print $i; exit}}')
    if [ -n "$cnt" ]; then upg_count=$cnt; fi
    samples=$(echo "$out" | grep -E "->|to be upgraded" | grep ":" | head -n 3 | cut -d: -f1 | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
elif [ -x /usr/bin/pacman ] || [ -x /bin/pacman ]; then
    out=$(pacman -Qu 2>/dev/null)
    cnt=$(echo "$out" | grep -c '^[a-zA-Z0-9]' || true)
    upg_count=$cnt
    samples=$(echo "$out" | head -n 3 | awk '{print $1}' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
elif [ -x /sbin/apk ] || [ -x /usr/bin/apk ]; then
    out=$(apk version -v -l '<' 2>/dev/null)
    cnt=$(echo "$out" | grep -c '<' || true)
    upg_count=$cnt
    samples=$(echo "$out" | grep '<' | head -n 3 | awk '{print $1}' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
elif [ -x /usr/bin/apt-get ]; then
    out=$(apt-get -s upgrade 2>/dev/null)
    cnt=$(echo "$out" | grep -c '^Inst ' || true)
    upg_count=$cnt
    samples=$(echo "$out" | grep '^Inst ' | head -n 3 | awk '{print $2}' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
elif [ -x /usr/bin/tdnf ]; then
    out=$(tdnf check-update 2>/dev/null || true)
    cnt=$(echo "$out" | grep -v -E '^Loading|^Refreshing|^$' | grep -c '^[a-zA-Z0-9]' || true)
    upg_count=$cnt
    samples=$(echo "$out" | grep -v -E '^Loading|^Refreshing|^$' | head -n 3 | awk '{print $1}' | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
elif [ -x /usr/bin/dnf ]; then
    out=$(dnf check-update 2>/dev/null || true)
    cnt=$(echo "$out" | grep -E '\.(aarch64|x86_64|noarch)' | wc -l || true)
    upg_count=$cnt
    samples=$(echo "$out" | grep -E '\.(aarch64|x86_64|noarch)' | head -n 3 | awk '{print $1}' | cut -d. -f1 | tr '\n' ',' | sed 's/,$//')
    if [ -n "$samples" ]; then upg_samples="$samples"; fi
fi

fu_count=0
fu_sample=""
reboot_required="false"
reboot_reason=""
if [ -f /var/run/reboot-required ] || [ -f /run/reboot-required ]; then
    reboot_required="true"
    reboot_reason="flag_file"
fi

samples_json=""
if [ -n "$upg_samples" ]; then
    old_ifs=$IFS
    IFS=','
    for s in $upg_samples; do
        s_trimmed=$(echo "$s" | tr -d ' ')
        [ -n "$s_trimmed" ] || continue
        if [ -n "$samples_json" ]; then
            samples_json="$samples_json,\"$s_trimmed\""
        else
            samples_json="\"$s_trimmed\""
        fi
    done
    IFS=$old_ifs
fi

printf '{"keys":[%s],"upg_count":%d,"upg_samples":[%s],"fu_count":%d,"fu_sample":"%s","reboot_required":%s,"reboot_reason":"%s"}\n' \
    "$keys_json" "$upg_count" "$samples_json" "$fu_count" "$fu_sample" "$reboot_required" "$reboot_reason"
'''


def probe_single_node(node: dict, debug: bool = False) -> dict:
    t0 = time.time()
    hname = node["name"]
    is_local = node.get("is_local", False)
    os_name = node.get("os", "Linux")
    mgr = node.get("mgr", "pkg")

    debug_info = {
        "ssh_cmd": "",
        "returncode": None,
        "stderr": "",
        "stdout": "",
        "error_type": "OK",
        "method": "unknown",
        "attempts": []
    }

    raw_out = ""
    try:
        if is_local:
            debug_info["method"] = "local_python"
            res = subprocess.run([sys.executable, "-c", REMOTE_PYTHON_PROBE], capture_output=True, text=True, timeout=5)
            debug_info["returncode"] = res.returncode
            debug_info["stderr"] = res.stderr.strip()
            debug_info["stdout"] = res.stdout.strip()
            raw_out = res.stdout.strip()
        else:
            targets_to_try = []
            if node.get("ssh_target"):
                targets_to_try.append(node["ssh_target"])
            host_val = node.get("host")
            if host_val:
                for u in [node.get("target_user"), "lab", "ansible", "labadmin", "root"]:
                    if not u:
                        continue
                    for k in [f"~/.ssh/{u}.key", "~/.ssh/ansible.key", "~/.ssh/id_user.key"]:
                        kp = Path(os.path.expanduser(k))
                        if kp.exists():
                            tgt_str = f"-i {kp} {u}@{host_val}"
                            if tgt_str not in targets_to_try:
                                targets_to_try.append(tgt_str)
                            break
                    tgt_simple = f"{u}@{host_val}"
                    if tgt_simple not in targets_to_try:
                        targets_to_try.append(tgt_simple)
                if host_val not in targets_to_try:
                    targets_to_try.append(host_val)

            success = False

            for cur_target in targets_to_try:
                # 拆分目標參數並展開 ~ 路徑
                target_args = []
                for token in shlex.split(cur_target):
                    if token.startswith("~"):
                        token = os.path.expanduser(token)
                    target_args.append(token)

                base_ssh = [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "LogLevel=ERROR",
                    "-o", "ConnectTimeout=3",
                ] + target_args

                # 嘗試 1: 使用 Python 探針 (直接調用，杜絕 shell 嵌套引號丟失 bug)
                py_cmd = base_ssh + ["python3 - 2>/dev/null || /usr/local/bin/python3 - 2>/dev/null || python -"]
                debug_info["ssh_cmd"] = " ".join(py_cmd)
                try:
                    res = subprocess.run(py_cmd, input=REMOTE_PYTHON_PROBE, capture_output=True, text=True, timeout=8)
                    debug_info["returncode"] = res.returncode
                    debug_info["stderr"] = res.stderr.strip()
                    debug_info["stdout"] = res.stdout.strip()
                    debug_info["attempts"].append({
                        "target": cur_target,
                        "method": "python3",
                        "code": res.returncode,
                        "stderr": res.stderr.strip()
                    })

                    if res.returncode == 0 and res.stdout.strip().startswith("{"):
                        raw_out = res.stdout.strip()
                        debug_info["method"] = "python3"
                        success = True
                        break

                    # 嘗試 2: 若無 Python 或回傳碼非 0，嘗試純 POSIX sh 探針
                    sh_cmd = base_ssh + ["sh"]
                    sh_res = subprocess.run(sh_cmd, input=REMOTE_POSIX_SH_PROBE, capture_output=True, text=True, timeout=8)
                    debug_info["attempts"].append({
                        "target": cur_target,
                        "method": "posix_sh",
                        "code": sh_res.returncode,
                        "stderr": sh_res.stderr.strip()
                    })
                    if sh_res.returncode == 0 and sh_res.stdout.strip().startswith("{"):
                        raw_out = sh_res.stdout.strip()
                        debug_info["method"] = "posix_sh"
                        debug_info["returncode"] = 0
                        success = True
                        break
                    else:
                        debug_info["stderr"] = sh_res.stderr.strip()
                        debug_info["returncode"] = sh_res.returncode
                except subprocess.TimeoutExpired:
                    debug_info["attempts"].append({"target": cur_target, "method": "timeout", "code": -1, "stderr": "Connection timed out"})
                except Exception as e:
                    debug_info["attempts"].append({"target": cur_target, "method": "exception", "code": -1, "stderr": str(e)})

                if success:
                    break
    except Exception as e:
        debug_info["stderr"] = str(e)
        debug_info["error_type"] = "EXCEPTION"

    el = time.time() - t0
    data = {
        "hostname": hname,
        "os": os_name,
        "package_manager": mgr,
        "status": "OFFLINE",
        "keys": [],
        "upg_count": 0,
        "upg_samples": [],
        "reboot_required": False,
        "reboot_reason": "",
        "elapsed": el,
        "debug_info": debug_info
    }

    if raw_out:
        try:
            parsed = json.loads(raw_out)
            data["status"] = "ONLINE"
            data["keys"] = parsed.get("keys", [])
            data["upg_count"] = parsed.get("upg_count", 0)
            data["upg_samples"] = parsed.get("upg_samples", [])
            data["reboot_required"] = parsed.get("reboot_required", False)
            data["reboot_reason"] = parsed.get("reboot_reason", "")
            debug_info["error_type"] = "OK"
        except Exception:
            debug_info["error_type"] = "JSON_PARSE_ERROR"
    else:
        # 分類錯誤原因
        err = debug_info.get("stderr", "").lower()
        if "permission denied" in err:
            debug_info["error_type"] = "SSH_AUTH_FAIL"
        elif "no route to host" in err or "could not resolve" in err or "connection refused" in err:
            debug_info["error_type"] = "HOST_UNREACHABLE"
        elif "password is required" in err:
            debug_info["error_type"] = "SUDO_PASSWORD_REQUIRED"
        elif "command not found" in err or "not found" in err:
            debug_info["error_type"] = "COMMAND_NOT_FOUND"
        elif debug_info.get("returncode") == 255:
            debug_info["error_type"] = "SSH_CONNECT_FAIL"
        elif not debug_info.get("error_type") or debug_info["error_type"] == "OK":
            debug_info["error_type"] = "TIMEOUT"

    return data


def probe_single_node_by_name(hostname: str, debug: bool = True) -> dict:
    """單獨探測指定節點 (除錯測試專用)"""
    target = next((t for t in CLUSTER_TARGETS if t["name"] == hostname or t["host"] == hostname), None)
    if not target:
        target = {"name": hostname, "host": hostname, "os": "Unknown", "mgr": "pkg"}
    return probe_single_node(target, debug=debug)


def probe_all_cluster_nodes(max_workers: int = 12, debug: bool = False) -> tuple:
    """
    並行活體探測全網 12 台節點之 authorized_keys 與即時更新狀態。
    回傳 (probe_results_dict, total_wall_clock_time)
    """
    t_start = time.time()
    targets = list(CLUSTER_TARGETS)
    if not targets:
        try:
            from core.gitea_api import fetch_remote_node_facts
            from core.config import get_ansible_user, _resolve_target_key_path
            remote_nodes, _, is_online = fetch_remote_node_facts()
            if is_online and remote_nodes:
                ans_u = get_ansible_user()
                for n in remote_nodes:
                    hname = n.get("hostname", "")
                    hip = n.get("primary_ip", hname)
                    if not hname or not hip:
                        continue
                    t_user = "root" if n.get("node_category") in ("appliance", "hypervisor") else ans_u
                    k_path = _resolve_target_key_path(t_user)
                    targets.append({
                        "name": hname,
                        "host": hip,
                        "os": n.get("distribution", n.get("os_family", "Linux")),
                        "mgr": "generic",
                        "pkg_manager": "generic",
                        "role": n.get("node_category", "server"),
                        "appliance_type": n.get("appliance_type", "none"),
                        "ssh_target": f"-i {k_path} {t_user}@{hip}",
                        "target_user": t_user,
                        "use_sudo": (t_user != "root"),
                        "is_local": (hname in ("control-node", "control-node") or hip in ("127.0.0.1", "localhost")),
                    })
        except Exception:
            pass

    def _worker(target):
        return probe_single_node(target, debug=debug)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker, targets))
    total_elapsed = time.time() - t_start

    # 轉為以 hostname 為 key 的字典
    out_map = {r["hostname"]: r for r in results}
    return out_map, total_elapsed
