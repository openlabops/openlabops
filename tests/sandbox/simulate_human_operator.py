#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
OpenLabOps - Human Operator Interactive Keystroke Simulation Suite
File: tests/sandbox/simulate_human_operator.py
==============================================================================
Testing Philosophy:
In production, a human engineer runs official CLI tools and types inputs
interactively by hand (manual typing).
In this test, the tool and keystrokes are 100% IDENTICAL to production,
with the only difference being that the infrastructure behind it is powered
by Dagger / sandbox containers (172.28.0.0/16) instead of real server hardware.

Covers:
1. Day-0 Master Installation Wizard (lab-init / lab-init) via Human Keystroke PTY.
2. Token display, /usr/local/bin/openlab/.gitea_token 0600 file creation, and Gitea Actions Secret setup.
3. Clean host verification: Zero empty downstream repos in /home/labadmin.
4. Day-2 Dynamic Node Onboarding (lab-node / lab-node) via Human Keystroke PTY.
5. Standard library only [INV-01], Production tooling only [INV-09].
==============================================================================
"""

import sys
import os
import pty
import time
import select
import stat
import json
import urllib.request
import urllib.error
import base64
from pathlib import Path

SANDBOX_DIR = Path(__file__).resolve().parent
REPO_ROOT = SANDBOX_DIR.parent.parent

# Detect binaries
INIT_BIN = REPO_ROOT / "bin" / "lab-init"
if not INIT_BIN.exists() and (REPO_ROOT / "bin" / "lab-init").exists():
    INIT_BIN = REPO_ROOT / "bin" / "lab-init"

NODE_BIN = REPO_ROOT / "bin" / "lab-node"
if not NODE_BIN.exists() and (REPO_ROOT / "bin" / "lab-node").exists():
    NODE_BIN = REPO_ROOT / "bin" / "lab-node"

STATUS_BIN = REPO_ROOT / "bin" / "lab-status"
if not STATUS_BIN.exists() and (REPO_ROOT / "bin" / "lab-status").exists():
    STATUS_BIN = REPO_ROOT / "bin" / "lab-status"

IS_OPENLAB = "openlab" in REPO_ROOT.name.lower()
DEFAULT_ORG = "OpenLabOps" if IS_OPENLAB else "OpenLabOps"
DEFAULT_PREFIX = "openlab" if IS_OPENLAB else "openlab"
GITEA_URL = os.environ.get("GITEA_URL", "http://172.28.0.2:3000")


def simulate_day0_init_interactive(init_bin: Path, gitea_url: str, org_name: str, repo_prefix: str, manifest_path: str = None, legacy_key_path: str = None) -> bool:
    print(f"\n{'='*72}")
    print(f"  [Simulator] Simulating Day-0 Human Interactive Wizard: {init_bin.name}")
    print(f"  Target Gitea: {gitea_url} | Target Org: {org_name} | Prefix: {repo_prefix}")
    if manifest_path:
        print(f"  Manifest: {manifest_path}")
    print(f"{'='*72}")

    master, slave = pty.openpty()
    pid = os.fork()

    if pid == 0:
        # Child: run official production tool in real controlling PTY
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)

        cmd = [str(init_bin)]
        if manifest_path:
            cmd.extend(["--manifest", str(manifest_path)])
        if legacy_key_path:
            cmd.extend(["--legacy-key", str(legacy_key_path)])
        os.execvp(str(init_bin), cmd)
        sys.exit(1)

    os.close(slave)
    session_log = []
    answered_prompts = set()
    start_t = time.time()
    last_output_t = time.time()

    def human_type(text):
        for char in text:
            os.write(master, char.encode("utf-8"))
            time.sleep(0.015)

    while time.time() - start_t < 180:
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 2048)
            except OSError:
                break
            if not data:
                break

            last_output_t = time.time()
            chunk = data.decode("utf-8", errors="replace")
            session_log.append(chunk)
            sys.stdout.write(chunk)
            sys.stdout.flush()

            recent = "".join(session_log)[-2000:]

            # Step 1: Base Parameters Prompts
            if ("Cluster Identification Name" in recent or "叢集識別名稱" in recent) and "p_cluster" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{org_name}\n")
                answered_prompts.add("p_cluster")

            elif ("Internal Domain" in recent or "內部解析網域" in recent) and "p_domain" not in answered_prompts:
                time.sleep(0.1)
                human_type("\n")
                answered_prompts.add("p_domain")

            elif ("System Administrator User" in recent or "系統管理員主帳號" in recent) and "p_admin" not in answered_prompts:
                time.sleep(0.1)
                human_type("labadmin\n")
                answered_prompts.add("p_admin")

            elif ("Automation Operations User" in recent or "自動化運維專用帳號" in recent) and "p_ansible" not in answered_prompts:
                time.sleep(0.1)
                human_type("ansible\n" if IS_OPENLAB else "lab\n")
                answered_prompts.add("p_ansible")

            elif ("Use existing" in recent or "是否已有現成運行的 Gitea" in recent) and "p_gitea_mode" not in answered_prompts:
                time.sleep(0.2)
                human_type("Y\n")
                answered_prompts.add("p_gitea_mode")

            elif ("Existing Gitea URL" in recent or "現有內部 Gitea URL" in recent or "Gitea Target URL" in recent) and "p_gitea_url" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{gitea_url}\n")
                answered_prompts.add("p_gitea_url")

            elif ("Gitea Organization" in recent or "Gitea 組織名稱" in recent) and "p_gitea_org" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{org_name}\n")
                answered_prompts.add("p_gitea_org")

            elif ("Gitea Admin Username" in recent or "Gitea 管理員帳號" in recent) and "p_gitea_user" not in answered_prompts:
                time.sleep(0.2)
                human_type("labadmin\n")
                answered_prompts.add("p_gitea_user")

            elif ("Gitea Admin Password" in recent or "Gitea 管理員密碼" in recent) and "p_gitea_pass" not in answered_prompts:
                time.sleep(0.2)
                human_type("labtest123\n")
                answered_prompts.add("p_gitea_pass")

            elif ("Repository Prefix" in recent or "倉庫命名前綴" in recent) and "p_repo_prefix" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{repo_prefix}\n")
                answered_prompts.add("p_repo_prefix")

            elif ("Associate/manage external GitHub" in recent or "是否關聯/納管外部 GitHub" in recent) and "p_github" not in answered_prompts:
                time.sleep(0.2)
                human_type("N\n")
                answered_prompts.add("p_github")

            elif ("是否由本精靈自動建立 Gitea Server 容器" in recent or "provision and start Gitea Server" in recent) and "p_opt_gitea" not in answered_prompts:
                time.sleep(0.2)
                human_type("N\n")
                answered_prompts.add("p_opt_gitea")

            elif ("provision and start Gitea Act Runner" in recent or "是否由本精靈自動建立 Gitea Act Runner" in recent or "是否自動建立並拉起 Gitea Act Runner" in recent) and "p_opt_runner" not in answered_prompts:
                time.sleep(0.2)
                human_type("N\n")
                answered_prompts.add("p_opt_runner")

            elif ("provision and start AGY-Remote" in recent or "是否由本精靈自動建立 AGY-Remote" in recent or "是否自動建立並拉起 AGY-Remote" in recent) and "p_opt_agy" not in answered_prompts:
                time.sleep(0.2)
                human_type("N\n")
                answered_prompts.add("p_opt_agy")

            elif ("Docker 運行主機 (" in recent or "Docker 運行主機:" in recent or "Docker Host Configuration" in recent or "Docker Host:" in recent) and "p_docker_host" not in answered_prompts:
                time.sleep(0.2)
                human_type("localhost\n")
                answered_prompts.add("p_docker_host")

            elif ("是否要針對連線失敗節點進行救援" in recent or "Rescue via Key or Password" in recent) and "p_rescue_prompt" not in answered_prompts:
                time.sleep(0.2)
                human_type("n\n")
                answered_prompts.add("p_rescue_prompt")

            # Step 4: Interactive Node Registration Prompts (Specific checks first)
            elif "Initial Password for labadmin@172.28.0.40" in recent and "p_node1_pass" not in answered_prompts:
                time.sleep(0.2)
                human_type("labtest123\n")
                answered_prompts.add("p_node1_pass")

            elif "Initial SSH User for 172.28.0.40" in recent and "p_node1_user" not in answered_prompts:
                time.sleep(0.2)
                human_type("labadmin\n")
                answered_prompts.add("p_node1_user")

            elif ("Confirm adding this node" in recent or "Confirm adding this node to OpenLabOps inventory" in recent):
                time.sleep(0.2)
                human_type("Y\n")

            elif ("Target Node IP (or 'done' to finish)" in recent or "Target Node IP" in recent):
                if "p_node1_ip" not in answered_prompts:
                    time.sleep(0.3)
                    human_type("172.28.0.40\n")  # mock-debian
                    answered_prompts.add("p_node1_ip")
                elif "p_node1_pass" in answered_prompts and "p_node_done" not in answered_prompts:
                    time.sleep(0.3)
                    human_type("done\n")
                    answered_prompts.add("p_node_done")

    try:
        os.close(master)
    except Exception:
        pass

    try:
        for _ in range(30):
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                exit_code = status >> 8
                break
            time.sleep(0.1)
        else:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            exit_code = 0
    except Exception:
        exit_code = 0

    full_output = "".join(session_log)
    success = (
        ("DAY-0 INITIALIZATION COMPLETE" in full_output) and
        ("GITEA AUTOMATION TOKEN ISSUED" in full_output)
    )
    print(f"\n[Simulator] Day-0 Interactive Session: {'SUCCESS [✓]' if success else 'FAILED [✗]'}")
    return success


def verify_post_initialization_invariants(gitea_url: str, org_name: str, repo_prefix: str) -> bool:
    print(f"\n{'='*72}")
    print(f"  [Simulator] Verifying Post-Initialization Production Invariants")
    print(f"{'='*72}")
    all_ok = True

    # 1. /usr/local/bin/openlab/.gitea_token exists and has 0600 mode
    user_token_file = Path("/usr/local/bin/openlab/.gitea_token")
    if not user_token_file.exists():
        print("  [✗] Invariant Failure: /usr/local/bin/openlab/.gitea_token does not exist!")
        all_ok = False
    else:
        mode = stat.S_IMODE(user_token_file.stat().st_mode)
        if mode != 0o600:
            print(f"  [✗] Invariant Failure: /usr/local/bin/openlab/.gitea_token mode is {oct(mode)}, expected 0600!")
            all_ok = False
        else:
            print(f"  [✓] Verified: /usr/local/bin/openlab/.gitea_token exists with 0600 strict permission.")

    # 2. Gitea Organization and 5 Downstream Repos exist
    auth_hdr = "Basic " + base64.b64encode(b"labadmin:labtest123").decode("ascii")
    base_api = gitea_url.rstrip("/")
    try:
        org_req = urllib.request.Request(
            f"{base_api}/api/v1/orgs/{org_name}",
            headers={"Authorization": auth_hdr, "User-Agent": "Test-Simulator"}
        )
        with urllib.request.urlopen(org_req, timeout=5) as resp:
            if resp.status == 200:
                print(f"  [✓] Verified: Gitea Organization '{org_name}' successfully provisioned.")
    except Exception as e:
        print(f"  [✗] Invariant Failure: Gitea Organization '{org_name}' check failed: {e}")
        all_ok = False

    expected_repos = ["ansible", "configs", "secrets", "tools", "workflows"]
    for r in expected_repos:
        r_name = f"{repo_prefix}-{r}"
        try:
            repo_req = urllib.request.Request(
                f"{base_api}/api/v1/repos/{org_name}/{r_name}",
                headers={"Authorization": auth_hdr, "User-Agent": "Test-Simulator"}
            )
            with urllib.request.urlopen(repo_req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("empty", True):
                    print(f"  [✓] Verified: Repository '{org_name}/{r_name}' exists and has code (not empty).")
                else:
                    print(f"  [✗] Invariant Failure: Repository '{org_name}/{r_name}' is empty (no commits pushed)!")
                    all_ok = False
        except Exception as e:
            print(f"  [✗] Invariant Failure: Repository '{org_name}/{r_name}' check failed: {e}")
            all_ok = False

    # 3. Org Actions Secrets: MASTER_TOKEN present, CI_TOKEN absent
    try:
        sec_req = urllib.request.Request(
            f"{base_api}/api/v1/orgs/{org_name}/actions/secrets",
            headers={"Authorization": auth_hdr, "User-Agent": "Test-Simulator"}
        )
        with urllib.request.urlopen(sec_req, timeout=5) as resp:
            sec_data = json.loads(resp.read().decode("utf-8"))
            sec_names = [s.get("name") for s in sec_data.get("secrets", sec_data)]
            if "MASTER_TOKEN" in sec_names:
                print("  [✓] Verified: Gitea Org Actions Secret 'MASTER_TOKEN' is properly registered.")
            else:
                print("  [✗] Invariant Failure: 'MASTER_TOKEN' missing from Gitea Org Actions Secrets!")
                all_ok = False

            if "CI_TOKEN" in sec_names:
                print("  [✗] Invariant Violation: 'CI_TOKEN' found in Org Actions Secrets (Must be edge-only)!")
                all_ok = False
            else:
                print("  [✓] Verified: 'CI_TOKEN' is strictly edge-only (not exposed in Actions Secrets).")
    except Exception as e:
        print(f"  [!] Note: Secrets inspection returned: {e}")

    # 4. Zero local directory clutter in /home/labadmin
    for r in expected_repos:
        r_dir = Path.home() / f"{repo_prefix}-{r}"
        if r_dir.exists():
            print(f"  [✗] Invariant Failure: Local directory {r_dir} was created in /home/labadmin!")
            all_ok = False
    if all_ok:
        print("  [✓] Verified: Clean host invariant maintained (Zero dummy repo directories in /home/labadmin).")

    # 5. Non-root user CLI status check
    if STATUS_BIN.exists():
        res = os.system(f"{STATUS_BIN} >/dev/null 2>&1")
        if res == 0:
            print(f"  [✓] Verified: Non-root {STATUS_BIN.name} execution succeeded with /usr/local/bin/openlab/.gitea_token.")
        else:
            print(f"  [✗] Invariant Failure: {STATUS_BIN.name} returned non-zero code {res}!")
            all_ok = False

    return all_ok


def simulate_node_add_session(target_ip="172.28.0.10", target_name="mock-arch", initial_user="labadmin", initial_password="labtest123") -> bool:
    target_user = "ansible" if IS_OPENLAB else "lab"
    print(f"\n{'='*72}")
    print(f"  [Simulator] Simulating Day-2 Dynamic Node Add: {target_name} ({target_ip})")
    print(f"{'='*72}")

    # Reset container to fresh state first
    os.system(f"docker exec {target_name} sh -c 'userdel -r {target_user} 2>/dev/null || deluser {target_user} 2>/dev/null || true; rm -rf /home/{target_user}; rm -f /home/labadmin/.ssh/authorized_keys /root/.ssh/authorized_keys' >/dev/null 2>&1")

    master, slave = pty.openpty()
    pid = os.fork()

    if pid == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)

        os.execvp(str(NODE_BIN), [str(NODE_BIN), "--onboard"])
        sys.exit(1)

    os.close(slave)
    session_log = []
    answered_prompts = set()
    start_t = time.time()

    def human_type(text):
        for char in text:
            os.write(master, char.encode("utf-8"))
            time.sleep(0.02)

    while time.time() - start_t < 35:
        r, _, _ = select.select([master], [], [], 0.05)
        if master in r:
            try:
                data = os.read(master, 2048)
            except OSError:
                break
            if not data:
                break

            chunk = data.decode("utf-8", errors="replace")
            session_log.append(chunk)
            sys.stdout.write(chunk)
            sys.stdout.flush()

            recent = "".join(session_log[-10:])

            if "Target Node IP or Hostname" in recent and "ip_entered" not in answered_prompts:
                time.sleep(0.3)
                human_type(f"{target_ip}\n")
                answered_prompts.add("ip_entered")

            elif "Initial SSH Username" in recent and "user_entered" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{initial_user}\n")
                answered_prompts.add("user_entered")

            elif "Choice [1]:" in recent and "auth_choice" not in answered_prompts:
                time.sleep(0.2)
                human_type("1\n")
                answered_prompts.add("auth_choice")

            elif "Enter initial password" in recent and "pass_entered" not in answered_prompts:
                time.sleep(0.3)
                human_type(f"{initial_password}\n")
                answered_prompts.add("pass_entered")

            elif "Target automated admin user" in recent and "target_user" not in answered_prompts:
                time.sleep(0.2)
                human_type(f"{target_user}\n")
                answered_prompts.add("target_user")

            elif "Confirm adding this node" in recent and "confirm_node" not in answered_prompts:
                time.sleep(0.4)
                human_type("Y\n")
                answered_prompts.add("confirm_node")

            elif "Re-compile Ansible inventory" in recent and "confirm_clf" not in answered_prompts:
                time.sleep(0.4)
                human_type("Y\n")
                answered_prompts.add("confirm_clf")

    try:
        os.close(master)
    except Exception:
        pass

    try:
        for _ in range(20):
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                exit_code = status >> 8
                break
            time.sleep(0.05)
        else:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            exit_code = 0
    except Exception:
        exit_code = 0

    full_output = "".join(session_log)
    success = ("Node Telemetry & Bootstrap Successfully Completed" in full_output)
    print(f"\n[Simulator] Node Add Session finished: {'SUCCESS [✓]' if success else 'FAILED [✗]'}")
    return success


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Human Operator Simulator")
    parser.add_argument("--manifest", help="Day-0 manifest path")
    parser.add_argument("--legacy-key", help="Legacy installer key path")
    args = parser.parse_args()

    print("=" * 76)
    print("  OpenLabOps Full Human Interactive Keystroke Simulation Suite")
    print(f"  Target Hub: {REPO_ROOT.name} | Gitea URL: {GITEA_URL}")
    print("=" * 76)

    # 1. Day-0 Master Wizard Simulation
    init_ok = simulate_day0_init_interactive(
        init_bin=INIT_BIN,
        gitea_url=GITEA_URL,
        org_name=DEFAULT_ORG,
        repo_prefix=DEFAULT_PREFIX,
        manifest_path=args.manifest,
        legacy_key_path=args.legacy_key
    )

    if not init_ok:
        print("\n[✗] Day-0 Human Interactive Wizard Simulation FAILED!")
        return 1

    # 2. Verify Post-Initialization Invariants
    post_ok = verify_post_initialization_invariants(
        gitea_url=GITEA_URL,
        org_name=DEFAULT_ORG,
        repo_prefix=DEFAULT_PREFIX
    )

    if not post_ok:
        print("\n[✗] Post-Initialization Invariants Verification FAILED!")
        return 1

    # 3. Day-2 Dynamic Node Onboarding Simulation (mock-arch)
    node_ok = simulate_node_add_session(target_ip="172.28.0.10", target_name="mock-arch")
    if not node_ok:
        print("\n[✗] Dynamic Node Onboarding Simulation FAILED!")
        return 1

    print("\n" + "=" * 76)
    print("  🎉 ALL HUMAN INTERACTIVE SIMULATION & INVARIANT TESTS PASSED [✓]")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
