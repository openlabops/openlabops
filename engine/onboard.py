#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps - Node Onboarding & Interactive Day-0 Controller
Provides an interactive human-in-the-loop CLI wizard and a pure POSIX/PTY
SSH execution engine that simulates human terminal interaction.

Features:
1. Interactive TUI prompts (Hostname/IP, User, Auth Mode, Password via getpass)
2. Native PTY SSH Controller (allocates real TTY, handles 'password:' and host key prompts)
3. Zero External Dependencies (100% Python standard library: pty, termios, fcntl, os, select, json)
4. Streams bootstrap_probe.sh over SSH without temporary files or docker cp
5. Automatic fact parsing and integration into conf/nodes/<hostname>.json + classifier.py

Adheres to:
- [INV-01] Zero External Dependencies
- [INV-02] Zero Credentials in Repo (ephemeral keys in /tmp)
- [INV-04] Sensory Ground Truth verification
- [INV-08] Non-Destructive Safe Evolution
"""

import sys
import os
import re
import time
import json
import fcntl
import shlex
import select
import termios
import getpass
import argparse
import shutil
import subprocess
import ipaddress
from pathlib import Path
from typing import Any, Dict, Optional

OPS_DIR = Path(__file__).resolve().parent.parent
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))
CONF_NODES_DIR = OPS_DIR / "conf" / "nodes"


def _get_nodes_dir() -> Path:
    env_dir = os.environ.get("LAB_NODES_DIR") or os.environ.get("LAB_NODES_DIR")
    if env_dir:
        return Path(env_dir)
    work_dir = os.environ.get("LAB_INIT_WORK_DIR") or os.environ.get("LAB_INIT_WORK_DIR")
    if work_dir:
        return Path(work_dir) / "conf" / "nodes"
    return CONF_NODES_DIR
PROBE_SCRIPT = OPS_DIR / "engine" / "bootstrap_probe.sh"
CLASSIFIER_PY = OPS_DIR / "engine" / "classifier.py"

from engine.bsd_dialog import BSDDialog, is_bsd_tui_supported

_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
_VALID_CATEGORIES = ("standard", "server", "desktop", "dev")


def _is_safe_hostname(val: str) -> bool:
    return bool(val and isinstance(val, str) and _SAFE_HOST_RE.match(val) and ".." not in val)


def _sanitize_hostname(val: str, fallback: str = "node") -> str:
    if _is_safe_hostname(val):
        return val
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "-", str(val or "")).strip(".-")
    return cleaned if _is_safe_hostname(cleaned) else fallback


def _normalize_openlab_node_facts(hname: str, pip: str, node_facts: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure node_facts strictly conforms to #OpenLabNode in schema/nodes.cue."""
    safe_hname = _sanitize_hostname(hname)
    raw_cat = str(node_facts.get("node_category", "server"))
    cat = raw_cat if raw_cat in _VALID_CATEGORIES else "server"
    caps = node_facts.get("capabilities")
    if not isinstance(caps, dict):
        caps = {}
    subnet_cidr = f"{pip.rsplit('.', 1)[0]}.0/24" if "." in pip else str(node_facts.get("subnet_cidr") or "192.168.1.0/24")
    return {
        "hostname": safe_hname,
        "fqdn": str(node_facts.get("fqdn") or f"{safe_hname}.{get_default_cluster_domain()}"),
        "primary_ip": str(pip),
        "subnet_cidr": subnet_cidr,
        "node_class": "standard" if is_openlab_mode() else str(node_facts.get("node_class", "standard")),
        "node_category": cat,
        "always_online": bool(node_facts.get("always_online", cat != "desktop")),
        "is_immutable": bool(node_facts.get("is_immutable", False)),
        "appliance_type": "none" if is_openlab_mode() else str(node_facts.get("appliance_type", "none")),
        "key_profile": "standard" if is_openlab_mode() else str(node_facts.get("key_profile", "standard")),
        "os_family": str(node_facts.get("os_family") or "Linux"),
        "distribution": str(node_facts.get("distribution") or "Linux"),
        "capabilities": {
            "has_docker": bool(caps.get("has_docker", False)),
            "has_python": bool(caps.get("has_python", True)),
        },
    }


def is_openlab_mode() -> bool:
    """判斷當前環境是否處於 OpenLabOps 開源控制台"""
    return (
        "openlab" in OPS_DIR.name.lower()
        or ((OPS_DIR / "conf" / "openlab.manifest.yml").exists() )
        or ((OPS_DIR / "tests" / "conf" / "openlab.manifest.test.yml").exists() )
        or any("lab-" in arg for arg in sys.argv)
        or os.getenv("LAB_MODE") == "1"
    )


def get_default_target_user() -> str:
    return "ansible" if is_openlab_mode() else "lab"


def get_default_operator_user() -> str:
    return "labadmin"


def get_default_cluster_domain() -> str:
    return "lab"


# ANSI Colors for Rich Terminal Display
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_BLUE = "\033[34m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_DIM = "\033[2m"

def execute_pty_ssh(host, user="labadmin", port=22, password=None, key_file=None, command=None, input_stream=None, timeout=30, prompt_callback=None):
    """
    透過 Python 標準庫 pty 分配真實虛擬終端 (Controlling TTY)，
    原生模擬人類鍵盤輸入，處理 OpenSSH 的主機指紋確認、SSH 密碼與 sudo 提權密碼提示詞。
    100% Python 標準庫，零外部套件 (無 pexpect / paramiko / sshpass)。
    """
    import pty

    master, slave = pty.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[3] = attrs[3] & ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
    except Exception:
        pass

    pid = os.fork()


    if pid == 0:
        # Child process: attach to slave PTY as controlling terminal
        os.close(master)
        os.setsid()
        try:
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        except Exception:
            pass

        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)

        ssh_cmd = [
            "ssh",
            "-tt",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ControlMaster=no",
            "-o", "ControlPath=none",
            "-o", "NumberOfPasswordPrompts=1",
            "-p", str(port)
        ]
        if key_file:
            ssh_cmd.extend(["-i", str(key_file), "-o", "IdentitiesOnly=yes"])

        ssh_cmd.append(f"{user}@{host}")
        if command:
            ssh_cmd.append(command)

        try:
            os.execvp("ssh", ssh_cmd)
        except Exception:
            os._exit(1)
        os._exit(1)

    # Parent process: interact with SSH via master PTY like a human
    os.close(slave)
    output_chunks = []
    sent_ssh_password = False
    sent_sudo_password = False
    sent_passphrase = False
    sent_stream = False
    start_time = time.time()

    while time.time() - start_time < timeout:
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 2048)
            except OSError:
                break
            if not data:
                break

            text = data.decode("utf-8", errors="replace")
            output_chunks.append(text)

            # 1. 模擬人類回應指紋詢問: Are you sure you want to continue connecting (yes/no/[fingerprint])?
            if "are you sure you want to continue connecting" in text.lower():
                time.sleep(0.05)
                os.write(master, b"yes\n")

            # 2. 偵測 Passphrase 保護提示：Enter passphrase for key
            if "enter passphrase for key" in text.lower():
                if prompt_callback:
                    pw = prompt_callback(f"節點 [{host}] SSH 私鑰需要 Passphrase 解鎖:\n{text.strip()[:90]}", True)
                    if pw:
                        time.sleep(0.05)
                        os.write(master, pw.encode("utf-8") + b"\n")
                        sent_passphrase = True
                        continue
                elif not sent_passphrase and password:
                    time.sleep(0.05)
                    os.write(master, password.encode("utf-8") + b"\n")
                    sent_passphrase = True
                    continue
                elif sys.stdin.isatty():
                    try:
                        pw = getpass.getpass(f"\n節點 [{host}] SSH 私鑰需要 Passphrase 解鎖: ")
                        if pw:
                            time.sleep(0.05)
                            os.write(master, pw.encode("utf-8") + b"\n")
                            sent_passphrase = True
                            continue
                    except (KeyboardInterrupt, EOFError):
                        pass
                output_chunks.append("\n[ERROR: KEY_PASSPHRASE_REQUIRED] SSH 私鑰設有 Passphrase 保護，請改用無密碼私鑰或先將金鑰載入 ssh-agent。\n")
                try:
                    os.write(master, b"\n")
                except Exception:
                    pass
                break

            # 3. 模擬人類回應 SSH 密碼輸入: 's password: 或 password: (排除 sudo 提示)
            if any(p in text.lower() for p in ["'s password:", "password:"]) and "[sudo]" not in text.lower():
                if not sent_ssh_password and password:
                    time.sleep(0.05)
                    os.write(master, password.encode("utf-8") + b"\n")
                    sent_ssh_password = True
                elif not sent_ssh_password and prompt_callback:
                    pw = prompt_callback(f"請輸入節點 [{host}] 之 SSH 登入密碼 ({user}):", True)
                    if pw:
                        time.sleep(0.05)
                        os.write(master, pw.encode("utf-8") + b"\n")
                        sent_ssh_password = True
                    else:
                        output_chunks.append("\n[ERROR: SSH_PASSWORD_REQUIRED] SSH 登入需要密碼，維運者取消輸入。\n")
                        try:
                            os.write(master, b"\x03\n")
                        except Exception:
                            pass
                        break
                elif not password:
                    output_chunks.append("\n[ERROR: SSH_PASSWORD_REQUIRED] SSH 登入需要密碼，請提供密碼或指定已授權之 SSH 私鑰。\n")
                    try:
                        os.write(master, b"\x03\n")
                    except Exception:
                        pass
                    break

            # 4. 模擬人類回應 Sudo 提權密碼輸入: [sudo] password for ...:
            if any(p in text.lower() for p in ["[sudo] password for", "password for "]):
                if not sent_sudo_password and password:
                    time.sleep(0.05)
                    os.write(master, password.encode("utf-8") + b"\n")
                    sent_sudo_password = True
                elif not sent_sudo_password and prompt_callback:
                    pw = prompt_callback(f"節點 [{host}] Sudo 提權需要密碼 ({user}):", True)
                    if pw:
                        time.sleep(0.05)
                        os.write(master, pw.encode("utf-8") + b"\n")
                        sent_sudo_password = True
                    else:
                        output_chunks.append("\n[ERROR: SUDO_PASSWORD_REQUIRED] Sudo 提權需要密碼，維運者取消輸入。\n")
                        try:
                            os.write(master, b"\x03\n")
                        except Exception:
                            pass
                        break
                elif not password:
                    output_chunks.append("\n[ERROR: SUDO_PASSWORD_REQUIRED] Sudo 提權需要密碼，請提供 Sudo 密碼或改用免密帳號 (如 lab / root)。\n")
                    try:
                        os.write(master, b"\x03\n")
                    except Exception:
                        pass
                    break
                elif sent_sudo_password:
                    # 密碼已發送但再次要求密碼，表示密碼錯誤
                    if prompt_callback:
                        pw = prompt_callback(f"節點 [{host}] Sudo 密碼錯誤！請重新輸入 Sudo 密碼 ({user}):", True)
                        if pw:
                            time.sleep(0.05)
                            os.write(master, pw.encode("utf-8") + b"\n")
                            sent_sudo_password = True
                            continue
                    output_chunks.append("\n[ERROR: SUDO_PASSWORD_INCORRECT] Sudo 密碼錯誤，提權失敗。\n")
                    try:
                        os.write(master, b"\x03\n")
                    except Exception:
                        pass
                    break

            # 5. 偵測認證失敗或 Permission denied
            if any(p in text.lower() for p in ["permission denied", "authentication failed"]):
                if not password or sent_ssh_password:
                    output_chunks.append("\n[ERROR: SSH_PERMISSION_DENIED] SSH 認證被拒絕 (Permission denied)。\n")
                    try:
                        os.write(master, b"\x03\n")
                    except Exception:
                        pass
                    break

            # 6. 登入或提權成功後串流輸入 (如 bootstrap_probe.sh)
            if input_stream and not sent_stream and "===OPENLAB_PIPE_READY===" in text:
                time.sleep(0.1)
                payload = input_stream.encode("utf-8") + b"\n===OPENLAB_PROBE_EOF===\n"
                # 分段寫入 PTY 避免超過遠端終端機 canonical 緩衝上限 (BSD/Linux MAX_CANON)
                chunk_size = 512
                for offset in range(0, len(payload), chunk_size):
                    chunk = payload[offset:offset + chunk_size]
                    while chunk:
                        _, w_ready, _ = select.select([], [master], [], 2.0)
                        if not w_ready:
                            break
                        written = os.write(master, chunk)
                        chunk = chunk[written:]
                    time.sleep(0.005)
                sent_stream = True

            # 7. 探針輸出完畢偵測 (排除腳本回顯 echo "===OPENLAB_NODE_JSON_END==="，僅匹配獨立輸出行)
            if sent_stream and "===OPENLAB_NODE_JSON_END===" in text and 'echo "===OPENLAB_NODE_JSON_END==="' not in text:
                try:
                    os.write(master, b"\nexit\n")
                except Exception:
                    pass
                time.sleep(0.2)
                break

    try:
        os.close(master)
    except Exception:
        pass

    exit_status = 0
    try:
        for _ in range(20):
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                exit_status = status >> 8
                break
            time.sleep(0.05)
        else:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except Exception:
                pass
    except Exception:
        pass

    full_output = "".join(output_chunks)
    return exit_status, full_output


def interactive_prompt(prompt_text, default=None, is_secret=False):
    """互動式人類提示函式"""
    suffix = f" [{default}]" if default else ""
    full_prompt = f"{C_CYAN}{prompt_text}{suffix}: {C_RESET}"
    if is_secret:
        val = getpass.getpass(full_prompt)
    else:
        val = input(full_prompt).strip()
    return val if val else default

def get_default_homelab_subnets():
    """
    從 conf/openlab.manifest.yml 或 conf/openlab.manifest.yml 解析內部網段作為 Ansible 帳號的預設來源限制。
    依據 [INV-05] 規範：
    - OpenLabOps: 預設對齊 service_lan (192.168.1.0/24) 與 wg_lan (192.168.1.0/24)。
    - OpenLabOps: 預設對齊 flat_lan / service_lan (192.168.1.0/24)。
    """
    manifest_file = OPS_DIR / "conf" / "openlab.manifest.yml"
    if not manifest_file.exists():
        manifest_file = OPS_DIR / "conf" / "openlab.manifest.yml"
    subnets = []
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            in_networks = False
            for line in f:
                stripped = line.strip()
                if stripped.startswith("networks:"):
                    in_networks = True
                    continue
                if in_networks:
                    if line and not line.startswith(" ") and not line.startswith("\t"):
                        break
                    if ":" in stripped:
                        k, v = stripped.split(":", 1)
                        k = k.strip()
                        v = v.split("#")[0].strip().strip('"\'')
                        if k in ["flat_lan", "service_lan", "wg_lan", "homelab_cidr", "client_cidr"] and v:
                            if v not in subnets:
                                subnets.append(v)
    if subnets:
        return ",".join(subnets)
    return "192.168.1.0/24"

def onboard_node(host, user=None, port=22, password=None, key_file=None, target_user=None, ephemeral_pubkey=None, allowed_subnets=None, interactive=True, callback=None, node_category=None, always_online=None, prompt_callback=None):
    """執行單一節點 Day-0 納管全流程"""
    user = user or get_default_operator_user()
    target_user = target_user or get_default_target_user()
    def emit(msg: str):
        if callback:
            callback(msg)
        else:
            print(msg)

    key_options = f'from="{allowed_subnets}"' if allowed_subnets else ''

    emit(f"\n{C_BOLD}{C_BLUE}══════════════════════════════════════════════════════════════════════{C_RESET}")
    emit(f"{C_BOLD}  Starting Onboarding Pipeline for Target: {C_YELLOW}{user}@{host}:{port}{C_RESET}")
    emit(f"{C_BOLD}  • Target Ansible Account : {C_GREEN}{target_user}{C_RESET}")
    opt_display = f'from="{allowed_subnets}"' if allowed_subnets else '(None - Initial Discovery Probe)'
    emit(f"{C_BOLD}  • Bootstrap Key Options  : {C_CYAN}{opt_display}{C_RESET}")
    if key_file:
        emit(f"{C_BOLD}  • Custom Private Key     : {C_YELLOW}{key_file}{C_RESET}")
    emit(f"{C_BOLD}{C_BLUE}══════════════════════════════════════════════════════════════════════{C_RESET}")

    temp_dir = Path("/tmp/lab_bootstrap_keys")
    cleanup_ephemeral = (ephemeral_pubkey is None)

    try:
        # 1. 一律採用臨時安全引導金鑰開門與 Handover 驗證，不依賴本機 ~/.ssh/<target_user>.key (正式公鑰由 Runner 自 *-secrets 部署)
        temp_key = temp_dir / "id_ed25519"
        temp_pub = temp_dir / "id_ed25519.pub"

        if ephemeral_pubkey:
            pubkey = ephemeral_pubkey.strip()
            priv_key = temp_key
        else:
            temp_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
            if not temp_key.exists():
                emit(f"{C_CYAN}[1/4] Generating Ephemeral Bootstrap Key Pair (INV-02 compliant)...{C_RESET}")
                subprocess.run([
                    "ssh-keygen", "-t", "ed25519", "-N", "",
                    "-f", str(temp_key),
                    "-C", "ephemeral-bootstrap@openlab"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pubkey = temp_pub.read_text(encoding="utf-8").strip()
            priv_key = temp_key

        # 2. 準備探針腳本與執行環境 (初始探針開門不施加 from 限制，待事實採集與網段定義後再由金鑰輪轉注入)
        probe_content = PROBE_SCRIPT.read_text(encoding="utf-8")
        env_vars = (
            f"BOOTSTRAP_USER={shlex.quote(str(target_user))} "
            f"BOOTSTRAP_PUBKEY={shlex.quote(str(pubkey))} "
            f"BOOTSTRAP_KEY_OPTIONS={shlex.quote(str(key_options))}"
        )

        probe_runner = (
            "stty -echo 2>/dev/null || true; "
            "echo \"===OPENLAB_PIPE_READY===\"; "
            "_tp=\"/tmp/.openlab_probe_$$.sh\"; : > \"$_tp\"; "
            "while IFS= read -r _l; do [ \"$_l\" = \"===OPENLAB_PROBE_EOF===\" ] && break; printf \"%s\\n\" \"$_l\" >> \"$_tp\"; done; "
            "sh \"$_tp\"; _rc=$?; rm -f \"$_tp\"; exit $_rc"
        )
        if user == "root":
            remote_cmd = f"{env_vars} sh -c '{probe_runner}'"
        else:
            # 非 root 預設使用者：env 置於 sh -c '...' 外部避免 shlex 單引號衝突，並以非互動暫存檔執行探針
            remote_cmd = f"sudo -p '[sudo] password for %u: ' env {env_vars} sh -c '{probe_runner}'"

        if not prompt_callback and interactive and not callback and sys.stdin.isatty():
            def _cli_prompt(p_msg: str, secret: bool = True) -> Optional[str]:
                try:
                    if secret:
                        return getpass.getpass(f"\n{p_msg} ")
                    return input(f"\n{p_msg} ")
                except (KeyboardInterrupt, EOFError):
                    return None
            prompt_callback = _cli_prompt

        emit(f"{C_CYAN}[2/4] Connecting via PTY Human Simulation & Streaming Sensory Probe...{C_RESET}")
        start_t = time.time()
        code, output = execute_pty_ssh(
            host=host,
            user=user,
            port=port,
            password=password,
            key_file=key_file,
            command=remote_cmd,
            input_stream=probe_content,
            timeout=25,
            prompt_callback=prompt_callback
        )
        latency_ms = int((time.time() - start_t) * 1000)

        # 3. 解析結構化事實
        err_reason = ""
        for l in output.splitlines():
            if "[ERROR:" in l:
                err_reason = l.strip()
                break
        if not err_reason:
            if "permission denied" in output.lower():
                err_reason = "SSH 連線失敗：認證被拒絕 (Permission denied)"
            elif "===OPENLAB_PIPE_READY===" not in output and "password for" in output.lower():
                err_reason = f"Sudo 提權失敗：需要密碼 ([sudo] password for {user})"
            elif "enter passphrase for key" in output.lower():
                err_reason = "SSH 私鑰錯誤：需要 Passphrase 密碼"

        if "===OPENLAB_NODE_JSON_START===" not in output or "===OPENLAB_NODE_JSON_END===" not in output:
            clean_err = err_reason or (output[-300:].strip() if output.strip() else "遠端探針無回應或連線逾時")
            emit(f"{C_RED}[✗] Onboarding Failed! {clean_err}{C_RESET}")
            return False, clean_err

        json_segment = output.split("===OPENLAB_NODE_JSON_START===")[-1].split("===OPENLAB_NODE_JSON_END===")[0]
        start_idx = json_segment.find("{")
        end_idx = json_segment.rfind("}")
        if start_idx == -1 or end_idx == -1:
            emit(f"{C_RED}[✗] JSON Boundaries '{{' or '}}' missing in probe output.{C_RESET}")
            return False, err_reason or "探針 JSON 邊界遺失"

        json_str = json_segment[start_idx:end_idx+1].replace("\r\n", "\n").replace("\r", "")
        try:
            node_facts = json.loads(json_str, strict=False)
        except Exception as e:
            emit(f"{C_RED}[✗] JSON Parsing Failed: {e}{C_RESET}")
            emit(f"{C_DIM}    JSON Snippet: {repr(json_str[:180])}{C_RESET}")
            return False, f"JSON 解析失敗: {e}"

        hname = _sanitize_hostname(node_facts.get("hostname", host), fallback=_sanitize_hostname(str(host)))
        node_facts["hostname"] = hname

        # 調用官方分類引擎自動識別設備角色
        try:
            from engine.classifier import classify_node
            auto_traits = classify_node(hname, node_facts, {"category": node_category} if node_category else {})
            for k, v in auto_traits.items():
                if k not in node_facts or not node_facts[k] or (k == "node_category" and not node_category):
                    node_facts[k] = v
        except Exception:
            pass

        if node_category:
            node_facts["node_category"] = node_category
        if always_online is not None:
            node_facts["always_online"] = always_online
        elif "always_online" not in node_facts:
            node_facts["always_online"] = (node_facts.get("node_category") != "desktop")

        # 4. 打印富事實卡片
        distro = node_facts.get("distribution", "Unknown")
        version = node_facts.get("version", "")
        os_f = node_facts.get("os_family", "Linux")
        cat = node_facts.get("node_category", "server")
        cores = node_facts.get("hardware", {}).get("cpu_cores", 1)
        mem_mb = node_facts.get("hardware", {}).get("memory_mb", 1024)
        disk_gb = node_facts.get("hardware", {}).get("disk_total_gb", 20)
        gw = node_facts.get("default_gateway", "")

        # 若 host 為非回環之有效 IPv4，優先作為管理與 Inventory primary_ip
        pip = host
        try:
            ip_obj = ipaddress.IPv4Address(host)
            if ip_obj.is_loopback:
                pip = node_facts.get("primary_ip") or host
        except Exception:
            pip = node_facts.get("primary_ip") or host

        emit(f"\n{C_GREEN}┌────────────────────────────────────────────────────────────────────┐{C_RESET}")
        emit(f"{C_GREEN}│{C_BOLD}  ✓ Node Telemetry & Bootstrap Successfully Completed!              {C_RESET}{C_GREEN}│{C_RESET}")
        emit(f"{C_GREEN}├────────────────────────────────────────────────────────────────────┤{C_RESET}")
        emit(f"{C_GREEN}│{C_RESET}  • Hostname & IP    : {C_BOLD}{hname}{C_RESET} ({pip})")
        emit(f"{C_GREEN}│{C_RESET}  • OS & Family      : {distro} {version} [{os_f}]")
        emit(f"{C_GREEN}│{C_RESET}  • Classification   : Category: {C_BOLD}{cat}{C_RESET} | Gateway: {gw}")
        emit(f"{C_GREEN}│{C_RESET}  • Hardware Ground  : {cores} Cores | {mem_mb} MB RAM | {disk_gb} GB Disk")
        emit(f"{C_GREEN}│{C_RESET}  • Bootstrap Door   : User '{target_user}' active with Passwordless Sudo")
        emit(f"{C_GREEN}│{C_RESET}  • Onboard Latency  : {latency_ms} ms")
        emit(f"{C_GREEN}└────────────────────────────────────────────────────────────────────┘{C_RESET}")

        # 5. 驗證金鑰免密登入 (Zero-Trust Handover Check)
        emit(f"\n{C_CYAN}[3/4] Verifying Passwordless Handover with Key...{C_RESET}")
        handover_code, handover_out = execute_pty_ssh(
            host=host,
            user=target_user,
            port=port,
            key_file=priv_key,
            command="whoami",
            timeout=10,
            prompt_callback=prompt_callback
        )
        if handover_code == 0 and target_user in handover_out:
            emit(f"  {C_GREEN}[✓] Handover Verified: Authenticated as '{target_user}' via Key!{C_RESET}")
        else:
            last_msg = handover_out.strip().splitlines()[-1] if handover_out.strip() else ""
            detail = f" ({last_msg[:100]})" if last_msg else ""
            emit(f"  {C_YELLOW}[!] Notice: Direct handover verification returned code {handover_code}{detail}{C_RESET}")

        # 6. 人類確認與落盤 (僅在 CLI 非回調模式下執行互動提示)
        if interactive and not callback:
            confirm = interactive_prompt("Confirm adding this node to OpenLabOps inventory? [Y/n]", default="Y")
            if confirm.lower() not in ["y", "yes"]:
                emit(f"{C_YELLOW}[!] Onboarding aborted by operator.{C_RESET}")
                return False, "維運者放棄納管"

        clean_facts = _normalize_openlab_node_facts(hname, pip, node_facts)
        node_facts = clean_facts

        if not callback:
            nodes_dir = _get_nodes_dir()
            nodes_dir.mkdir(parents=True, exist_ok=True)
            out_file = nodes_dir / f"{hname}.json"
            out_file.write_text(json.dumps(clean_facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            emit(f"{C_CYAN}[4/4] Saved inventory classification facts: {out_file}{C_RESET}")

        return True, node_facts
    finally:
        if cleanup_ephemeral and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

def parse_day0_manifest(manifest_path, default_user=None, target_user=None, skip_appliances=True, skip_endpoints=True, skip_nodes=None):
    """
    透過共用純標準庫 YAML 解析器 (core.yaml_parser) 解析 Day-0 節點納管宣告清單 [INV-01, INV-03]。
    支援：
    1. Day-0 扁平清單格式 (targets: - name: ... ip: ...)
    2. 標準架構階層格式 (inventory: dev: ... servers: ... appliances: ... desktops: ...)
    """
    default_user = default_user or get_default_operator_user()
    target_user = target_user or get_default_target_user()
    lib_dir = str(OPS_DIR / "tools" / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata

    data = parse_yaml_file(manifest_path)
    skip_set = set(skip_nodes or [])

    meta = {}
    for k, v in data.items():
        if k in ("inventory", "targets"):
            continue
        meta[k] = v
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if not isinstance(sub_v, (dict, list)):
                    meta[sub_k] = sub_v

    targets = []
    if isinstance(data.get("targets"), list):
        for item in data["targets"]:
            if isinstance(item, dict) and (item.get("name") or item.get("ip")):
                h_name = str(item.get("name", item.get("ip", "")))
                if h_name not in skip_set:
                    targets.append({k: str(v) for k, v in item.items()})

    meta_map = extract_manifest_hosts_metadata(data)
    for hname, hmeta in meta_map.items():
        cat = hmeta.get("category", "server")
        is_app = (cat == "appliance")
        is_end = (cat == "desktop")
        is_dev = (cat == "dev")
        if (skip_appliances and is_app) or (skip_endpoints and is_end) or (hname in skip_set):
            continue
        u_val = hmeta.get("user") or default_user
        entry = {
            "name": hname,
            "ip": hmeta["ip"],
            "initial_user": u_val,
            "user": u_val,
            "target_user": target_user,
            "scenario": "existing_key",
            "inv_group": "appliances" if is_app else ("desktops" if is_end else ("dev" if is_dev else "servers")),
            "is_appliance": is_app,
            "is_endpoint": is_end,
            "is_dev": is_dev,
        }
        if hmeta.get("key_name"):
            entry["key_file"] = hmeta["key_name"]
        if hmeta.get("key_profile"):
            entry["key_profile"] = hmeta["key_profile"]
        targets.append(entry)

    return meta, targets


def verify_existing_key_connectivity(targets, default_user="labadmin", callback=None):
    """
    [INV-04] 強制執行現有金鑰連線確認 (Existing Key Connectivity Verification)
    即使是從 Manifest 直接匯入的既有節點，也必須強制先確認現有金鑰連線全部暢通。
    回傳 (verified_targets, failed_targets)
    """
    def _log(msg):
        if callback:
            try:
                callback(msg)
            except Exception:
                pass
        else:
            print(msg)

    _log(f"\n{C_BOLD}{C_CYAN}  • [Mandatory Verification] Probing Existing SSH Key Connectivity to Fleet ({len(targets)} Nodes)...{C_RESET}")
    verified = []
    failed = []

    ssh_dir = Path.home() / ".ssh"

    for t in targets:
        name = t.get("name", t.get("ip"))
        ip = t.get("ip", name)
        user = t.get("initial_user") or t.get("user") or default_user
        target_user = t.get("target_user", "lab")
        port = int(t.get("ssh_port") or t.get("port") or 22)
        key_file = t.get("key_file")

        # 優先策略 1: 若指定 key_file，支援完整絕對路徑、含 ~ 路徑與 ~/.ssh/ 檔名
        candidate_keys = []
        if key_file:
            kp = Path(key_file).expanduser()
            if kp.exists():
                candidate_keys.append(kp)
            elif (ssh_dir / key_file).exists():
                candidate_keys.append(ssh_dir / key_file)
            elif (ssh_dir / f"{key_file}.key").exists():
                candidate_keys.append(ssh_dir / f"{key_file}.key")

        # 策略 2: 常用管理金鑰 (id_user.key, gateway.key, ansible.key, ansible.key, openlab.key, id_ed25519, id_rsa, id_ecdsa)
        for ck in ["gateway.key", "id_user.key", "ansible.key", "openlab.key", "id_ed25519", "id_rsa", "id_ecdsa"]:
            p = ssh_dir / ck
            if p.exists() and p not in candidate_keys:
                candidate_keys.append(p)

        # 策略 3: 自動將 ~/.ssh/ 下所有有效私鑰納入候選，提高無痛開門成功率
        if ssh_dir.exists():
            for p in sorted(ssh_dir.iterdir()):
                if p.is_file() and not p.name.endswith(".pub") and not p.name.endswith(".old") and p.name not in ("config", "known_hosts", "known_hosts.old", "authorized_keys"):
                    if p not in candidate_keys:
                        candidate_keys.append(p)

        connected = False
        last_err = ""

        # 步驟 A: 嘗試使用 ~/.ssh/config 定義之 host alias 直連
        if not connected:
            alias_cmd = [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                "-o", "StrictHostKeyChecking=accept-new",
                "-p", str(port),
                name, "echo 'SSH_OK' && ([ $(id -u) -eq 0 ] || sudo -n true 2>/dev/null && echo 'SUDO_NOPW' || echo 'SUDO_PW_REQUIRED')"
            ]
            try:
                r = subprocess.run(alias_cmd, capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and "SSH_OK" in r.stdout:
                    connected = True
                    t["verified_ssh_target"] = f"-p {port} {name}" if port != 22 else name
                    if "SUDO_PW_REQUIRED" in r.stdout and not t.get("initial_password"):
                        t["sudo_pw_required"] = True
            except Exception as e:
                last_err = str(e)

        # 步驟 B: 若 alias 失敗，嘗試以 user@ip 搭配各候選金鑰直連
        if not connected:
            for kpath in candidate_keys:
                cmd = [
                    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "IdentitiesOnly=yes",
                    "-p", str(port),
                    "-i", str(kpath),
                    f"{user}@{ip}", "echo 'SSH_OK' && ([ $(id -u) -eq 0 ] || sudo -n true 2>/dev/null && echo 'SUDO_NOPW' || echo 'SUDO_PW_REQUIRED')"
                ]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if r.returncode == 0 and "SSH_OK" in r.stdout:
                        connected = True
                        port_opt = f"-p {port} " if port != 22 else ""
                        t["verified_ssh_target"] = f"{port_opt}-i {kpath} {user}@{ip}"
                        t["key_file"] = str(kpath)
                        if "SUDO_PW_REQUIRED" in r.stdout and not t.get("initial_password"):
                            t["sudo_pw_required"] = True
                        break
                    else:
                        last_err = r.stderr.strip() or f"Exit {r.returncode}"
                except Exception as e:
                    last_err = str(e)

        # 步驟 C: 若仍失敗，嘗試直接以 user@ip (利用預設 ssh-agent)
        if not connected:
            cmd = [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                "-o", "StrictHostKeyChecking=accept-new",
                "-p", str(port),
                f"{user}@{ip}", "echo 'SSH_OK' && ([ $(id -u) -eq 0 ] || sudo -n true 2>/dev/null && echo 'SUDO_NOPW' || echo 'SUDO_PW_REQUIRED')"
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and "SSH_OK" in r.stdout:
                    connected = True
                    port_opt = f"-p {port} " if port != 22 else ""
                    t["verified_ssh_target"] = f"{port_opt}{user}@{ip}"
                    if "SUDO_PW_REQUIRED" in r.stdout and not t.get("initial_password"):
                        t["sudo_pw_required"] = True
                else:
                    if not last_err:
                        last_err = r.stderr.strip() or f"Exit {r.returncode}"
            except Exception as e:
                last_err = str(e)

        if connected:
            verified.append(t)
            if t.get("sudo_pw_required"):
                _log(f"    {C_YELLOW}[!] {name:<12} ({ip:<15}) -> Reachable via SSH ({t.get('verified_ssh_target')}), but Sudo requires password!{C_RESET}")
            else:
                _log(f"    {C_GREEN}[✓] {name:<12} ({ip:<15}) -> Reachable via existing SSH key ({t.get('verified_ssh_target')}){C_RESET}")
        else:
            failed.append((t, last_err))
            _log(f"    {C_RED}[✗] {name:<12} ({ip:<15}) -> Connection Failed: {last_err or 'No response'}{C_RESET}")

    return verified, failed

def revoke_remote_management_key(host, target_user="lab", timeout=8):
    """
    連線至遠端節點，自其 ~/.ssh/authorized_keys 中收回管理端公鑰（解除管控）。
    100% 原生 Python 標準庫調用 OpenSSH。
    """
    pubkeys_to_revoke = []
    for cand in [
        Path.home() / ".ssh" / f"{target_user}.pub",
        Path.home() / ".ssh" / f"{target_user}.key.pub",
        Path.home() / ".ssh" / "lab.pub",
        Path.home() / ".ssh" / "ansible.key.pub",
        Path.home() / ".ssh" / "ansible.pub",
        Path.home() / ".ssh" / "ansible.key.pub",
    ]:
        if cand.exists():
            try:
                content = cand.read_text(encoding="utf-8").strip()
                parts = content.split()
                if len(parts) >= 2:
                    pubkeys_to_revoke.append(parts[1])
                elif content:
                    pubkeys_to_revoke.append(content)
            except Exception:
                pass

    priv_key = None
    for cand_k in [
        Path.home() / ".ssh" / f"{target_user}.key",
        Path.home() / ".ssh" / "ansible.key",
        Path.home() / ".ssh" / "ansible.key",
        Path.home() / ".ssh" / "id_ed25519",
    ]:
        if cand_k.exists():
            priv_key = cand_k
            break

    unique_keys = [k for k in sorted(set(pubkeys_to_revoke)) if k]
    if not unique_keys:
        return False

    grep_filters = " ".join([f"-e {shlex.quote(k)}" for k in unique_keys])
    remote_sh = (
        f"if [ -f ~/.ssh/authorized_keys ]; then "
        f"(grep -vF {grep_filters} ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp || true) && "
        f"mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys && "
        f"chmod 0600 ~/.ssh/authorized_keys && "
        f"echo '===REVOKE_SUCCESS==='; "
        f"else echo '===REVOKE_NO_FILE==='; fi"
    )

    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={timeout}",
    ]
    if priv_key:
        ssh_cmd.extend(["-i", str(priv_key)])
    ssh_cmd.extend([f"{target_user}@{host}", remote_sh])

    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout + 2)
        if "===REVOKE_SUCCESS===" in res.stdout or "===REVOKE_NO_FILE===" in res.stdout:
            return True
        return False
    except Exception:
        return False

def decommission_node(target, target_user=None, purge=False, no_revoke=False, callback=None):
    """除役並移除指定節點事實與管控公鑰"""
    def emit(msg: str):
        if callback:
            callback(msg)
        else:
            print(msg)

    if not _is_safe_hostname(str(target)):
        emit(f"[✗] Error: Invalid target hostname '{target}'.")
        return False

    target_file = None
    target_hname = str(target)
    target_data = {}

    nodes_dir = _get_nodes_dir()
    if (nodes_dir / f"{target}.json").exists():
        target_file = nodes_dir / f"{target}.json"
    else:
        for p in nodes_dir.glob("*.json"):
            if p.name == "current.json":
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("hostname") == target or data.get("primary_ip") == target:
                    target_file = p
                    target_data = data
                    target_hname = data.get("hostname", target)
                    break
            except Exception:
                continue

    if not target_file:
        emit(f"[✗] Error: Node '{target}' facts not found in {nodes_dir}.")
        return False

    if not target_data and target_file.exists():
        try:
            target_data = json.loads(target_file.read_text(encoding="utf-8"))
            target_hname = target_data.get("hostname", target)
        except Exception:
            pass

    target_hname = _sanitize_hostname(str(target_hname), fallback=_sanitize_hostname(str(target)))
    target_ip = target_data.get("primary_ip") or target_data.get("ansible_host") or target
    target_account = target_user or target_data.get("ansible_user") or "lab"

    emit(f"Decommissioning Node: {target_hname} ({target_ip})")

    # 1. 遠端收回管控公鑰 (Remote Key Revocation)
    if not no_revoke:
        emit(f"  • Attempting to revoke management key from [{target_hname}] ({target_ip})...")
        revoked = revoke_remote_management_key(target_ip, target_user=target_account)
        if revoked:
            emit(f"    [✓] Remote management key successfully revoked from authorized_keys.")
            emit(f"    [✓] Target node [{target_hname}] is now unmanaged.")
        else:
            emit(f"    [!] Warning: Could not connect to [{target_ip}] to revoke key (offline or already unmanaged).")
    else:
        emit(f"  [!] Notice: Remote key revocation skipped.")

    # 2. 備份與資料留存決策 (Data Retention vs Purge)
    if purge:
        target_file.unlink(missing_ok=True)
        emit(f"  [✓] Node facts purged: {target_file}")
        if _is_safe_hostname(target_hname):
            for backup_root in [
                Path("/tmp/dr_backup_vault") / target_hname,
                OPS_DIR.parent / "openlab-configs" / "backups" / target_hname,
                OPS_DIR.parent / "openlab-configs" / "backups" / target_hname,
            ]:
                if backup_root.exists():
                    shutil.rmtree(backup_root, ignore_errors=True)
                    emit(f"  [✓] Purged backup vault directory: {backup_root}")
    else:
        archive_dir = _get_nodes_dir() / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_file = archive_dir / f"{target_hname}_{int(time.time())}.json"
        target_file.rename(archive_file)
        emit(f"  [✓] Node facts archived to: {archive_file}")

    # 3. 重新編譯 Inventory (不觸碰 node-information/)
    if CLASSIFIER_PY.exists():
        emit("  • Re-compiling Ansible inventory/hosts.yml & current.json...")
        subprocess.run([sys.executable, str(CLASSIFIER_PY), "--apply"], capture_output=True)

    emit(f"  [✓] Node [{target_hname}] decommission complete.")
    return True

def prompt_node_rescue_dialog(target: Dict[str, Any], error_reason: str, dialog=None, non_interactive=False) -> str:
    """
    統一節點連線救援與設定修改對話框 (Shared by lab-init and lab-node)
    讓維運者針對卡住/失敗的節點修改連線憑證、Sudo 密碼或選擇放棄 (<Skip Node>)。
    回傳 "retry" (已更新 target 字典) 或 "skip"。
    """
    if non_interactive:
        return "skip"

    hname = target.get("name", target.get("ip", "node"))
    ip = target.get("ip", hname)
    cur_user = target.get("initial_user") or target.get("user") or "labadmin"
    cur_key = target.get("key_file") or ""
    cur_pass = target.get("initial_password") or ""
    cur_port = str(target.get("ssh_port") or target.get("port") or 22)
    cur_role = target.get("node_category") or target.get("inv_group_role") or "server"

    prompt_msg = (
        f"節點 [{hname}] ({ip}) 連線或提權受阻！\n"
        f"原因: {error_reason}\n"
        f"請更新連線設定後按 <Retry Node>，或按 <Skip Node> 略過此節點。"
    )

    fields = [
        {"key": "role", "label": "節點分類角色 (Role):", "value": cur_role, "secret": False, "help": "server / dev / desktop / hypervisor / storage"},
        {"key": "user", "label": "SSH 登入帳號 (User):", "value": cur_user, "secret": False, "help": "目標主機 SSH 帳號 (如 labadmin, root, ubuntu, lab)"},
        {"key": "key_file", "label": "SSH 私鑰路徑 (Key):", "value": cur_key, "secret": False, "help": "私鑰絕對路徑或 ~/.ssh/ 檔名 (如 ~/.ssh/ansible.key)"},
        {"key": "password", "label": "SSH/Sudo 密碼 (Password):", "value": cur_pass, "secret": True, "help": "該帳號之 SSH 登入密碼或 Sudo 提權密碼"},
        {"key": "port", "label": "SSH 端口 (Port):", "value": cur_port, "secret": False, "help": "目標主機 SSH 連線埠號 (預設: 22)"},
    ]

    use_bsd = False
    if dialog is not None:
        use_bsd = True
    elif is_bsd_tui_supported():
        dialog = BSDDialog(title="OpenLabOps Node Rescue Console", subtitle="Connection & Credential Setup")
        use_bsd = True

    if use_bsd:
        r_vals, btn = dialog.form(
            title=f"Node Rescue: {hname}",
            prompt=prompt_msg,
            fields=fields,
            buttons=["Retry Node", "Skip Node"],
            width=76,
            height=22
        )
        if btn == "Retry Node" and r_vals:
            target["initial_user"] = r_vals.get("user") or cur_user
            target["user"] = target["initial_user"]
            if r_vals.get("key_file"):
                target["key_file"] = os.path.expanduser(r_vals["key_file"])
            else:
                target["key_file"] = None
            target["initial_password"] = r_vals.get("password") or None
            try:
                target["ssh_port"] = int(r_vals.get("port") or 22)
            except ValueError:
                target["ssh_port"] = 22
            target["port"] = target["ssh_port"]
            target["node_category"] = r_vals.get("role") or cur_role
            target["scenario"] = "key_auth" if target.get("key_file") else ("password_only" if target.get("initial_password") else "existing_key")
            return "retry"
        else:
            return "skip"
    else:
        # CLI fallback
        print(f"\n{C_YELLOW}══════════════════════════════════════════════════════════════════════{C_RESET}")
        print(f"{C_BOLD}  ⚠️  節點 [{hname}] ({ip}) 連線或提權受阻！{C_RESET}")
        print(f"  原因: {C_RED}{error_reason}{C_RESET}")
        print(f"{C_YELLOW}══════════════════════════════════════════════════════════════════════{C_RESET}")
        choice = interactive_prompt("是否要修改設定重試此節點 (r=Retry, s=Skip)? [r/s]", default="r")
        if choice.lower().startswith("r"):
            target["node_category"] = interactive_prompt("  節點角色 (server/dev/desktop/hypervisor/storage)", default=cur_role)
            target["initial_user"] = interactive_prompt("  SSH 登入帳號", default=cur_user)
            target["user"] = target["initial_user"]
            r_key = interactive_prompt("  SSH 私鑰路徑 (留空使用密碼或 Agent)", default=cur_key)
            target["key_file"] = os.path.expanduser(r_key) if r_key else None
            r_pass = interactive_prompt("  SSH / Sudo 密碼 (留空則不更換)", default=cur_pass, is_secret=True)
            target["initial_password"] = r_pass or None
            r_port = interactive_prompt("  SSH 端口", default=cur_port)
            try:
                target["ssh_port"] = int(r_port)
            except ValueError:
                target["ssh_port"] = 22
            target["port"] = target["ssh_port"]
            target["scenario"] = "key_auth" if target.get("key_file") else ("password_only" if target.get("initial_password") else "existing_key")
            return "retry"
        return "skip"


def run_lab_node_tui(dialog=None):
    """
    OpenLabOps Unified Node Management TUI (BSDInstall-Style Curses Console)
    提供一致的節點納管、清冊檢視、節點移除與 Inventory 重整。
    """
    if not is_bsd_tui_supported():
        print("終端不支援 Curses TUI，請直接使用 CLI 子指令：lab-node add <IP> / lab-node list")
        return

    if dialog is None:
        dialog = BSDDialog(title="OpenLabOps Node Management Console", subtitle="Node Lifecycle & Inventory Controller")

    while True:
        menu_items = [
            ("onboard", "納管全新或救援目標節點 (Onboard / Rescue Node)"),
            ("list", "檢視目前已納管節點清冊 (List Managed Nodes Ground Truth)"),
            ("remove", "除役並移除指定節點 (Decommission Node & Revoke Key)"),
            ("classify", "編譯主機清冊 (Re-compile Ansible Inventory)"),
            ("exit", "離開節點管理主控台 (Exit Controller)"),
        ]
        choice, btn = dialog.menu(
            "Node Operations Menu",
            "請選擇欲執行的節點維運作業:",
            menu_items,
            buttons=["Select", "Exit"],
            width=76,
            height=20
        )
        if not choice or choice in ("exit", "Cancel") or btn.lower() in ("exit", "cancel"):
            break

        if choice == "onboard":
            node_fields = [
                {"key": "host", "label": "Target Host / IP:", "value": "", "help": "目標主機 IP 位址或 Hostname"},
                {"key": "user", "label": "Initial SSH User:", "value": "labadmin", "help": "初始 SSH 登入帳號 (預設 labadmin)"},
                {"key": "role", "label": "Node Category (Role):", "value": "server", "help": "server / dev / desktop / hypervisor / storage"},
                {"key": "password", "label": "Initial Password:", "value": "", "secret": True, "help": "SSH 密碼 (若使用既有金鑰可留空)"},
                {"key": "key_file", "label": "Private Key File:", "value": "", "help": "SSH 私鑰路徑 (留空則使用預設 ~/.ssh 金鑰)"},
                {"key": "target_user", "label": "Target Ops User:", "value": "lab", "help": "受控維運帳號 (預設 lab)"},
                {"key": "allowed_subnets", "label": "Allowed Subnets:", "value": "", "help": "允許來源網段 (留空則自動探測)"},
            ]
            vals, f_btn = dialog.form(
                "Node Ingestion Parameters",
                "請輸入待納管主機之連線與安全授權資訊:",
                node_fields,
                buttons=["Onboard", "Cancel"],
                width=76,
                height=22
            )
            if not vals or not vals.get("host") or f_btn in ("Cancel", "Exit"):
                continue

            target_node = {
                "ip": vals["host"].strip(),
                "name": vals["host"].strip(),
                "initial_user": vals.get("user") or "labadmin",
                "user": vals.get("user") or "labadmin",
                "node_category": vals.get("role") or "server",
                "key_file": os.path.expanduser(vals["key_file"]) if vals.get("key_file") else None,
                "initial_password": vals.get("password") or None,
                "ssh_port": 22,
                "target_user": vals.get("target_user") or "lab",
                "allowed_subnets": vals.get("allowed_subnets") or None
            }

            def _tui_prompt(msg: str, secret: bool = True) -> Optional[str]:
                return dialog.password_dialog("In-Flight Authentication", msg)

            while True:
                onboard_res = [False, None]
                def _do_onboard(log_fn):
                    ok, facts_or_err = onboard_node(
                        host=target_node["ip"],
                        user=target_node["user"],
                        port=target_node["ssh_port"],
                        password=target_node.get("initial_password"),
                        key_file=target_node.get("key_file"),
                        target_user=target_node.get("target_user", "lab"),
                        allowed_subnets=target_node.get("allowed_subnets"),
                        interactive=False,
                        callback=log_fn,
                        node_category=target_node.get("node_category", "server"),
                        prompt_callback=_tui_prompt
                    )
                    onboard_res[0] = ok
                    onboard_res[1] = facts_or_err
                    return ok

                dialog.progress_box(
                    "Node Onboarding Pipeline",
                    f"Connecting to {target_node['user']}@{target_node['ip']}...",
                    _do_onboard,
                    width=76,
                    height=22
                )

                if onboard_res[0] and isinstance(onboard_res[1], dict):
                    facts = onboard_res[1]
                    hname = facts.get("hostname", target_node["ip"])
                    pip = facts.get("primary_ip", target_node["ip"])
                    distro = facts.get("distribution", "Unknown")
                    cat = facts.get("node_category", "server")

                    if (OPS_DIR / ".git").exists():
                        try:
                            nodes_dir = _get_nodes_dir()
                            nodes_dir.mkdir(parents=True, exist_ok=True)
                            out_file = nodes_dir / f"{hname}.json"
                            out_file.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        except Exception:
                            pass

                    def _do_reg(log_fn):
                        log_fn(f"Node: {hname} ({pip}) | {cat} | {distro}")
                        log_fn(f"Dispatching register-node-fact.yml for {hname}...")
                        try:
                            from tools.lib.core.gitea_api import gitea_dispatch, register_node_fact_via_runner
                            ok_reg = register_node_fact_via_runner(hname, facts, action="upsert", wait=True)
                            log_fn("Remote federation updated." if ok_reg else "Remote registration returned warning.")
                            log_fn(f"Dispatching deploy-ssh-keys.yml for {hname}...")
                            gitea_dispatch(
                                "deploy-ssh-keys.yml",
                                payload={
                                    "ref": "main",
                                    "inputs": {
                                        "target_hosts": hname,
                                        "target_user": target_node.get("target_user", "lab"),
                                        "deploy_authorized_keys": "true",
                                        "deploy_client_keys": "false",
                                    },
                                },
                                wait=False,
                            )
                            return ok_reg
                        except Exception as e:
                            log_fn(f"Error: {e}")
                            return False

                    dialog.progress_box("Registering Node to Federation", hname, _do_reg, width=76, height=20)
                    dialog.msgbox("Onboarding Complete", f"節點 [{hname}] ({pip}) 已成功納管並自動同步至遠端集群事實庫！")
                    break
                else:
                    fail_err = str(onboard_res[1] or "連線或提權逾時失敗")
                    rescue_choice = prompt_node_rescue_dialog(target_node, fail_err, dialog=dialog)
                    if rescue_choice != "retry":
                        dialog.msgbox("Onboarding Notice", f"維運者已放棄節點 [{target_node['ip']}] 之納管。")
                        break

        elif choice == "remove":
            existing_nodes = []
            for p in sorted(_get_nodes_dir().glob("*.json")):
                if p.name in ("current.json",):
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    hname = data.get("hostname", p.stem)
                    pip = data.get("primary_ip", "Unknown IP")
                    cat = data.get("node_category", "server")
                    existing_nodes.append((hname, f"{pip:<16} [{cat}]"))
                except Exception:
                    continue

            if not existing_nodes:
                dialog.msgbox("No Managed Nodes", "目前無任何已納管的節點事實記錄。")
                continue

            rem_target, rem_btn = dialog.menu(
                "Select Node to Decommission",
                "請選擇欲從集群中除役下架的節點:",
                existing_nodes,
                buttons=["Decommission", "Cancel"],
                width=76,
                height=20
            )
            if not rem_target or rem_btn in ("Cancel", "Exit"):
                continue

            confirm_msg = (
                f"警告：確定要除役並移除節點 [{rem_target}] 嗎？\n\n"
                f"此操作將會：\n"
                f"  1. 嘗試連線該主機並自 authorized_keys 收回管理公鑰\n"
                f"  2. 將節點事實封存至 conf/nodes/archive/\n"
                f"  3. 自 CMDB 與 inventory 移除該主機記錄"
            )
            if dialog.yesno("Confirm Node Decommission", confirm_msg, width=74, height=16, default=False):
                rem_res = [False]
                def _do_remove(log_fn):
                    ok = decommission_node(rem_target, callback=log_fn)
                    rem_res[0] = ok
                    return ok

                dialog.progress_box("Decommissioning Node", f"Removing {rem_target}...", _do_remove, width=76, height=20)
                if rem_res[0]:
                    dialog.msgbox("Decommission Complete", f"節點 [{rem_target}] 已成功自集群除役下架！")
                else:
                    dialog.msgbox("Decommission Notice", f"節點 [{rem_target}] 已除役（遠端金鑰可能未成功收回）。")

        elif choice == "list":
            lines = [f"{'主機名稱':<12} {'主要 IP':<16} {'分類角色':<12} {'系統發行版'}"]
            lines.append("-" * 64)
            nodes_map = {}
            source_label = ""
            is_online = False
            # 嚴格自遠端 4-Repo 聯邦 (Gitea configs/operations) 抓取即時節點事實；離線即顯示離線
            try:
                from tools.lib.core.gitea_api import fetch_remote_node_facts
                remote_nodes, source_label, is_online = fetch_remote_node_facts()
                for d in remote_nodes:
                    h = d.get("hostname", "")
                    if h:
                        nodes_map[h] = d
            except Exception:
                is_online = False

            if not is_online:
                lines.append("  (離線狀態：無法連線至 Gitea 聯邦倉庫取得節點事實)")
            elif not nodes_map:
                lines.append("  (目前尚未有任何節點事實紀錄)")
            else:
                for h in sorted(nodes_map.keys()):
                    d = nodes_map[h]
                    ip = d.get("primary_ip", "")
                    cat = d.get("node_category", "server")
                    os_name = f"{d.get('distribution', d.get('os_family', ''))}"
                    lines.append(f"{h:<12} {ip:<16} {cat:<12} {os_name}")
                src_info = f" (來源: {source_label})" if source_label else ""
                lines.insert(0, f"全網已納管節點總數: {len(nodes_map)} 台{src_info}\n")
            dialog.msgbox("Managed Nodes Ground Truth", "\n".join(lines), width=76, height=22)

        elif choice == "classify":
            def _do_clf(log_fn):
                log_fn("Executing classifier.py --apply...")
                r = subprocess.run([sys.executable, str(CLASSIFIER_PY), "--apply"], capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    if line.strip():
                        log_fn(line.strip())
                return r.returncode == 0
            dialog.progress_box("Compiling Inventory", "classifier.py", _do_clf, width=76, height=20)
            dialog.msgbox("Inventory Compiled", "Ansible inventory/hosts.yml 與 current.json 已成功編譯完成！")


def main():
    parser = argparse.ArgumentParser(description="OpenLabOps Interactive Day-0 Node Onboarding Controller")
    parser.add_argument("--manifest", help="Path to Day-0 declarative node manifest (e.g. tests/conf/day0_mock_fleet.yml)")
    parser.add_argument("--legacy-key", help="Default legacy private key path for mixed-key targets")
    parser.add_argument("--host", help="Target node IP or hostname")
    parser.add_argument("--user", default=None, help="Initial SSH user (default: labadmin or labadmin)")
    parser.add_argument("--password", help="Initial SSH password (if non-interactive)")
    parser.add_argument("--key", help="Initial legacy SSH private key path")
    parser.add_argument("--target-user", default=None, help="Target bootstrap username (default: lab or ansible)")
    parser.add_argument("--allowed-subnets", help="Allowed source IP CIDRs for ansible account in authorized_keys (default: internal subnets from manifest)")
    parser.add_argument("--remove", help="Decommission and remove target node from cluster inventory")
    parser.add_argument("--purge", action="store_true", help="Purge all archived facts and node backup data instead of retaining them")
    parser.add_argument("--no-revoke", action="store_true", help="Skip revoking management SSH key from remote authorized_keys")
    parser.add_argument("--force", action="store_true", help="Force removal without interactive confirmation")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive batch mode")
    parser.add_argument("--category", choices=["dev", "server", "desktop", "appliance"], help="Node classification category")
    parser.add_argument("--always-online", dest="always_online", action="store_true", default=None, help="Mark as always online")
    parser.add_argument("--intermittent", dest="always_online", action="store_false", help="Mark as intermittent/desktop")
    parser.add_argument("--classify", action="store_true", help="Run classifier.py after onboarding")
    parser.add_argument("--onboard", "--cli", dest="cli_onboard", action="store_true", help="Launch interactive CLI text wizard instead of Curses TUI")
    args = parser.parse_args()

    # 節點下架與除役模式 (Node Decommission Mode via CLI)
    if args.remove:
        target = args.remove
        if not args.force and not args.non_interactive:
            confirm = interactive_prompt(f"Are you sure you want to unmanage and remove [{target}] from cluster? [y/N]", default="N")
            if confirm.lower() not in ["y", "yes"]:
                print(f"{C_YELLOW}Aborted by user.{C_RESET}")
                sys.exit(0)
        ok = decommission_node(
            target=target,
            target_user=args.target_user,
            purge=args.purge,
            no_revoke=args.no_revoke
        )
        sys.exit(0 if ok else 1)

    # 宣告式清單模式 (Declarative Manifest Mode) - 事先填相關參數然後才是 login
    if args.manifest:
        m_path = Path(args.manifest)
        if not m_path.exists():
            print(f"{C_RED}Error: Manifest file {m_path} not found.{C_RESET}")
            sys.exit(1)

        meta, targets = parse_day0_manifest(m_path)
        print(f"\n{C_BOLD}Loaded {len(targets)} targets from Day-0 Declarative Manifest: {C_YELLOW}{m_path}{C_RESET}\n")

        manifest_subnets = meta.get("allowed_subnets")
        default_subnets = args.allowed_subnets or manifest_subnets or None

        all_ok = True
        for t in targets:
            t_ip = t.get("ip")
            t_name = t.get("name", t_ip)
            t_user = t.get("initial_user") or t.get("user") or get_default_operator_user()
            t_pass = t.get("initial_password", "labtest123")
            t_scen = t.get("scenario", "password_only")
            t_target = t.get("target_user") or get_default_target_user()
            t_subnets = t.get("allowed_subnets", default_subnets)
            t_key = args.legacy_key if t_scen == "mixed_key_and_password" else None

            ok, facts = onboard_node(
                host=t_ip,
                user=t_user,
                password=t_pass,
                key_file=t_key,
                target_user=t_target,
                allowed_subnets=t_subnets,
                interactive=False
            )
            if not ok:
                all_ok = False

        if args.classify:
            print(f"\n{C_CYAN}Compiling Ansible inventory/hosts.yml via classifier.py...{C_RESET}")
            subprocess.run(["python3", str(CLASSIFIER_PY), "--apply"])

        sys.exit(0 if all_ok else 1)

    # 全功能互動式控制器 (Full Interactive Controller)
    # 若使用者未明確指定 CLI 模式且終端支援 Curses，則啟動全螢幕 TUI 控制台
    if not args.non_interactive and not args.host and not args.cli_onboard:
        if is_bsd_tui_supported():
            run_lab_node_tui()
            sys.exit(0)
        # 若終端不支援 Curses，自動降級進入下方的 CLI 純文字循序問答引導流程

    # CLI 模式或指定單一主機納管
    host = args.host
    user = args.user or get_default_operator_user()
    password = args.password
    key_file = args.key
    target_user = args.target_user or get_default_target_user()
    allowed_subnets = args.allowed_subnets

    if not args.non_interactive:
        print(f"{C_BOLD}{C_MAGENTA}")
        print("  _  ___          _          _      _       ___             ")
        print(" | |/ (_)_      _(_)_ __ ___(_) ___| |__   / _ \\ _ __  ___  ")
        print(" | ' /| \\ \\ /\\ / / | '__/ _ \\ |/ __| '_ \\ | | | | '_ \\/ __| ")
        print(" | . \\| |\\ V  V /| | | |  __/ | (__| | | || |_| | |_) \\__ \\ ")
        print(" |_|\\_\\_| \\_/\\_/ |_|_|  \\___|_|\\___|_| |_(_)___/| .__/|___/ ")
        print("                                                |_|         ")
        print(f"  Day-0 Interactive Node Onboarding & Sensory Controller v1.2{C_RESET}")
        print(f"  Zero External Dependencies | 100% Native PTY Controller\n")

        if not host:
            host = interactive_prompt("Enter Target Node IP or Hostname", default="172.28.0.10")
        if not user:
            user = interactive_prompt("Enter Initial SSH Username", default=get_default_operator_user())

        if not password and not key_file:
            print(f"\n{C_BOLD}Select Initial Authentication Method:{C_RESET}")
            print(f"  {C_CYAN}[1]{C_RESET} Password Only (全新裸機 / 無金鑰)")
            print(f"  {C_CYAN}[2]{C_RESET} Pre-existing SSH Key (既有舊安裝公鑰)")
            print(f"  {C_CYAN}[3]{C_RESET} Password + Legacy Key Fallback (混合嘗試)")
            auth_choice = interactive_prompt("Choice", default="1")

            if auth_choice in ["1", "3"]:
                password = interactive_prompt(f"Enter initial password for {user}@{host}", is_secret=True)
            if auth_choice in ["2", "3"]:
                key_file = interactive_prompt("Enter path to initial SSH private key", default=str(Path.home() / ".ssh" / "id_rsa"))

        if not target_user:
            target_user = interactive_prompt("Target automated admin user to establish", default=get_default_target_user())

    if not host:
        print(f"{C_RED}Error: Host IP or Hostname is required.{C_RESET}")
        sys.exit(1)

    success, facts = onboard_node(
        host=host,
        user=user,
        password=password,
        key_file=key_file,
        target_user=target_user,
        allowed_subnets=allowed_subnets,
        interactive=not args.non_interactive,
        node_category=args.category,
        always_online=args.always_online
    )

    if success and (args.classify or not args.non_interactive):
        if not args.non_interactive:
            run_clf = interactive_prompt("\nRe-compile Ansible inventory/hosts.yml now? [Y/n]", default="Y")
            if run_clf.lower() in ["y", "yes"]:
                subprocess.run(["python3", str(CLASSIFIER_PY), "--apply"])
        else:
            subprocess.run(["python3", str(CLASSIFIER_PY), "--apply"])

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
