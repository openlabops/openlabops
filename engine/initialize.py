#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
OpenLabOps Master Operations Engine: Day-0 Initialization Wizard (bin/lab-init)
==============================================================================
Governed by docs/architecture/incubator-and-initialization-spec.md & [INV-09].

Lifecycle Architecture (100% Python Standard Library - Zero External Dependencies):
  1. Base Information Setup: Interactive TUI / Declarative Manifest input.
  2. Ephemeral Bootstrap Key: Generates temporary key in /tmp/lab_bootstrap_keys/.
  3. Dynamic Node Ingestion (lab-node):
     - Logs into target node (labadmin/root via password or legacy key).
     - Injects bootstrap_probe.sh with ephemeral key (NO from IP limitation!).
     - Collects ground truth facts (Hardware, OS, and live Network Interfaces/IPs/Gateway).
  4. Subnet Analysis & Classifier:
     - Discovers actual subnets and generates inventory/hosts.yml.
     - Confirms subnet naming and mappings.
  5. Official Key Generation & Rotation Handover (Action / Playbook driven):
     - Generates official permanent production key (ansible.key).
     - Injects official key WITH defined Homelab internal subnets restriction (from="...").
     - Verifies connection using permanent key.
     - Completely wipes the ephemeral bootstrap key from authorized_keys.
     - Purges /tmp/lab_bootstrap_keys/ (Zero Residual).
  6. Readiness Dashboard: Displays complete cluster operational status.
==============================================================================
"""

import os
import re
import sys
import json
import time
import shlex
import shutil
import base64
import getpass
from typing import Optional
import tempfile
import argparse
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# Paths & Directories
ENGINE_DIR = Path(__file__).resolve().parent
OPS_DIR = ENGINE_DIR.parent
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))
CONF_DIR = OPS_DIR / "conf"
CONF_NODES_DIR = CONF_DIR / "nodes"
INVENTORY_DIR = OPS_DIR / "ansible" / "inventory"


def _get_work_dir() -> Optional[Path]:
    val = os.environ.get("LAB_INIT_WORK_DIR") or os.environ.get("KIWI_INIT_WORK_DIR")
    return Path(val) if val else None


def _get_nodes_dir() -> Path:
    wd = _get_work_dir()
    return (wd / "conf" / "nodes") if wd else CONF_NODES_DIR


def _get_inventory_dir() -> Path:
    wd = _get_work_dir()
    return (wd / "ansible" / "inventory") if wd else INVENTORY_DIR


def _get_tools_config_path() -> Path:
    wd = _get_work_dir()
    if not wd:
        return OPS_DIR / "tools" / "conf" / "tools.config.json"
    work_cfg = wd / "tools" / "conf" / "tools.config.json"
    if not work_cfg.exists():
        src_cfg = OPS_DIR / "tools" / "conf" / "tools.config.json"
        if src_cfg.exists():
            work_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_cfg, work_cfg)
    return work_cfg

# Internationalization (i18n)
from engine.i18n import (
    t,
    get_locale,
    set_locale,
    detect_system_locale,
    SUPPORTED_LOCALES
)

# ANSI Colors for Rich TUI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"


def ui_banner():
    print(f"\n{C_BOLD}{C_CYAN}╔══════════════════════════════════════════════════════════════════════╗")
    print("║        OpenLabOps Master Operations Engine: Day-0 Init Wizard         ║")
    print("║     Zero External Dependencies | 100% Native Production Suite        ║")
    print(f"╚══════════════════════════════════════════════════════════════════════╝{C_RESET}\n")


def interactive_prompt(prompt_text, default=None, is_secret=False):
    suffix = f" [{default}]" if default else ""
    full_prompt = f"{C_CYAN}{prompt_text}{suffix}: {C_RESET}"
    if is_secret:
        if sys.stdin.isatty():
            val = getpass.getpass(full_prompt)
        else:
            print(full_prompt, end="", flush=True)
            val = sys.stdin.readline().strip()
    else:
        val = input(full_prompt).strip()
    return val if val else default


def step_header(step_num, total_steps, title):
    print(f"\n{C_BOLD}{C_BLUE}[Step {step_num}/{total_steps}] {title}{C_RESET}")
    print(f"{C_DIM}{'─' * 60}{C_RESET}")


def validate_github_token(token):
    """驗證 GitHub PAT 有效性並取得登入身分 (100% Python 標準庫)"""
    if not token:
        return False, "Empty token"
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "OpenLabOps-Operations-Engine",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data.get("login", "unknown")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)


FEDERATION_REPO_TYPES = ["operations", "workflows", "configs", "secrets"]


def ensure_gitea_organization(base_url, auth_str, org_name):
    """
    確保 Gitea 組織存在，若不存在則主動透過 REST API 建立。
    100% Python 3 標準庫 [INV-01]，冪等安全。
    """
    check_req = urllib.request.Request(
        f"{base_url}/api/v1/orgs/{org_name}",
        headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"}
    )
    try:
        with urllib.request.urlopen(check_req, timeout=5) as resp:
            if resp.status == 200:
                return True, "Already Exists"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)

    payload = json.dumps({
        "username": org_name,
        "visibility": "public",
        "description": "OpenLabOps Private Cloud Infrastructure Organization",
        "repo_admin_change_team_access": True
    }).encode("utf-8")
    create_req = urllib.request.Request(
        f"{base_url}/api/v1/orgs",
        data=payload,
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "User-Agent": "OpenLabOps-Init"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(create_req, timeout=5) as resp:
            if resp.status in (200, 201):
                return True, "Created"
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return True, "Already Exists"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)

    return False, "Failed to create organization"


def provision_gitea_ci_bot(base_url, auth_str, gitea_user, gitea_password, org_name, repo_prefix):
    """
    透過 Gitea REST API 自動簽發具備 Write 權限之自動化 Token，並加入組織與團隊。
    落地至 /usr/local/bin/{repo_prefix}/.gitea_token 與 ~/.gitea_token (0600)。
    """
    import secrets
    bot_user = "ci-bot"
    parsed_g_host = urllib.parse.urlparse(base_url).hostname or "openlab.local"
    bot_email = f"ci-bot@{parsed_g_host}"
    bot_password = f"ci_bot_{secrets.token_hex(16)}"

    # 解析真實 username
    actual_username = gitea_user
    try:
        user_req = urllib.request.Request(
            f"{base_url}/api/v1/user",
            headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"}
        )
        with urllib.request.urlopen(user_req, timeout=5) as resp:
            if resp.status == 200:
                u_data = json.loads(resp.read().decode("utf-8"))
                actual_username = u_data.get("username", u_data.get("login", gitea_user))
    except Exception:
        pass

    # 1. 建立或確認 ci-bot 使用者
    create_user_payload = json.dumps({
        "source_id": 0,
        "login_name": bot_user,
        "username": bot_user,
        "email": bot_email,
        "password": bot_password,
        "must_change_password": False,
        "visibility": "private"
    }).encode("utf-8")

    user_req = urllib.request.Request(
        f"{base_url}/api/v1/admin/users",
        data=create_user_payload,
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "User-Agent": "OpenLabOps-Init"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(user_req, timeout=5) as resp:
            pass
    except urllib.error.HTTPError as e:
        if e.code == 409:
            # ci-bot 已存在，由管理員重設其密碼確保後續 Token 簽發順利
            try:
                patch_payload = json.dumps({"password": bot_password, "login_name": bot_user, "source_id": 0}).encode("utf-8")
                patch_req = urllib.request.Request(
                    f"{base_url}/api/v1/admin/users/{bot_user}",
                    data=patch_payload,
                    headers={
                        "Authorization": f"Basic {auth_str}",
                        "Content-Type": "application/json",
                        "User-Agent": "OpenLabOps-Init"
                    },
                    method="PATCH"
                )
                with urllib.request.urlopen(patch_req, timeout=5):
                    pass
            except Exception:
                pass
    except Exception:
        pass

    # 2. 依據 [docs/security/action-secrets-spec.md] 4.3 節規範：
    #    A. 將 ci-bot 加入組織
    try:
        org_member_req = urllib.request.Request(
            f"{base_url}/api/v1/orgs/{org_name}/members/{bot_user}",
            headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"},
            method="PUT"
        )
        with urllib.request.urlopen(org_member_req, timeout=5):
            pass
    except Exception:
        pass

    #    B. 依據 Step 2.2 規範：若 ci-bot 存在於 Owners 團隊，必須立即移除 (確保非 Admin/Owner)
    try:
        teams_req = urllib.request.Request(
            f"{base_url}/api/v1/orgs/{org_name}/teams",
            headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"}
        )
        with urllib.request.urlopen(teams_req, timeout=5) as t_resp:
            if t_resp.status == 200:
                teams = json.loads(t_resp.read().decode("utf-8"))
                for tm in teams:
                    if tm.get("name") in ("Owners", "owners"):
                        owners_id = tm.get("id")
                        del_owner_req = urllib.request.Request(
                            f"{base_url}/api/v1/teams/{owners_id}/members/{bot_user}",
                            headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"},
                            method="DELETE"
                        )
                        try:
                            with urllib.request.urlopen(del_owner_req, timeout=5):
                                pass
                        except Exception:
                            pass
                        break
    except Exception:
        pass

    bot_team_id = None
    try:
        # C. 查詢 CI-Dispatchers 團隊
        teams_req = urllib.request.Request(
            f"{base_url}/api/v1/orgs/{org_name}/teams",
            headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"}
        )
        with urllib.request.urlopen(teams_req, timeout=5) as t_resp:
            if t_resp.status == 200:
                teams = json.loads(t_resp.read().decode("utf-8"))
                for tm in teams:
                    if tm.get("name") in ("CI-Dispatchers", "ci-dispatchers"):
                        bot_team_id = tm.get("id")
                        break

        # D. 若專屬 CI-Dispatchers 寫入團隊不存在，建立最小權限團隊 (permission: write, 嚴格限定 prefix-workflows 專庫)
        if not bot_team_id:
            create_team_payload = json.dumps({
                "name": "CI-Dispatchers",
                "description": "Automated workflow dispatchers (Isolated strictly to workflows repository)",
                "permission": "write",
                "can_create_org_repo": False,
                "includes_all_repositories": False
            }).encode("utf-8")
            create_team_req = urllib.request.Request(
                f"{base_url}/api/v1/orgs/{org_name}/teams",
                data=create_team_payload,
                headers={"Authorization": f"Basic {auth_str}", "Content-Type": "application/json", "User-Agent": "OpenLabOps-Init"},
                method="POST"
            )
            with urllib.request.urlopen(create_team_req, timeout=5) as ct_resp:
                if ct_resp.status in (200, 201):
                    ct_data = json.loads(ct_resp.read().decode("utf-8"))
                    bot_team_id = ct_data.get("id")

        # E. 實體隔離：將團隊唯一綁定至 prefix-workflows 倉庫 (嚴格禁止綁定 operations / secrets)
        if bot_team_id:
            workflows_repo = f"{repo_prefix}-workflows"
            add_repo_req = urllib.request.Request(
                f"{base_url}/api/v1/teams/{bot_team_id}/repos/{org_name}/{workflows_repo}",
                headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"},
                method="PUT"
            )
            try:
                with urllib.request.urlopen(add_repo_req, timeout=5):
                    pass
            except Exception:
                pass

            # F. 將 ci-bot 加入 CI-Dispatchers 團隊
            add_team_req = urllib.request.Request(
                f"{base_url}/api/v1/teams/{bot_team_id}/members/{bot_user}",
                headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"},
                method="PUT"
            )
            with urllib.request.urlopen(add_team_req, timeout=5):
                pass
    except Exception:
        pass

    # 3. 簽發 ci-bot 專用受限 Token (依規範由 ci-bot 帳號簽發，非管理員帳號)
    token_name = f"{repo_prefix}-ci-token-{int(time.time())}"
    token_payload = json.dumps({
        "name": token_name,
        "scopes": ["all"]
    }).encode("utf-8")

    ci_token = ""

    # 優先調用 Admin API 為 ci-bot 簽發 Token
    admin_token_req = urllib.request.Request(
        f"{base_url}/api/v1/admin/users/{bot_user}/tokens",
        data=token_payload,
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "User-Agent": "OpenLabOps-Init"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(admin_token_req, timeout=5) as resp:
            if resp.status in (200, 201):
                data = json.loads(resp.read().decode("utf-8"))
                ci_token = data.get("sha1", data.get("token", ""))
    except Exception:
        pass

    # 備援：ci-bot 自身 Basic Auth 簽發
    if not ci_token:
        bot_auth = base64.b64encode(f"{bot_user}:{bot_password}".encode("utf-8")).decode("ascii")
        bot_token_req = urllib.request.Request(
            f"{base_url}/api/v1/users/{bot_user}/tokens",
            data=token_payload,
            headers={
                "Authorization": f"Basic {bot_auth}",
                "Content-Type": "application/json",
                "User-Agent": "OpenLabOps-Init"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(bot_token_req, timeout=5) as resp:
                if resp.status in (200, 201):
                    data = json.loads(resp.read().decode("utf-8"))
                    ci_token = data.get("sha1", data.get("token", ""))
        except Exception:
            pass

    # 4. 自動寫入本機 Token 檔案 (0600, atomic os.open)
    if ci_token:
        def _write_atomic_secret(secret_path: Path, secret_val: str):
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(secret_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.fchmod(fd, 0o600)
                os.write(fd, (secret_val.strip() + "\n").encode("utf-8"))
            finally:
                os.close(fd)

        # A. 寫入 /usr/local/bin/{repo_prefix}/.gitea_token (規格唯一指定路徑)
        sys_token_file = Path(f"/usr/local/bin/{repo_prefix}/.gitea_token")
        try:
            _write_atomic_secret(sys_token_file, ci_token)
        except Exception:
            try:
                import pwd
                cur_user = pwd.getpwuid(os.getuid()).pw_name
                subprocess.run(["sudo", "mkdir", "-p", str(sys_token_file.parent)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(
                    ["sudo", "tee", str(sys_token_file)],
                    input=(ci_token.strip() + "\n").encode("utf-8"),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                subprocess.run(["sudo", "chown", cur_user, str(sys_token_file)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "chmod", "0600", str(sys_token_file)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"    {C_YELLOW}[!] Warning: Could not write {sys_token_file}: {e}{C_RESET}")

        # C. 寫入 Gitea URL 到系統路徑 /usr/local/bin/{repo_prefix}/.gitea_url
        for u_path in [Path.home() / ".gitea_url", Path(f"/usr/local/bin/{repo_prefix}/.gitea_url")]:
            try:
                u_path.parent.mkdir(parents=True, exist_ok=True)
                u_path.write_text(base_url.strip() + "\n", encoding="utf-8")
                u_path.chmod(0o644)
            except Exception:
                pass

        # D. 動態更新 tools.config.json 內部 URL、組織與聯邦倉庫 (寫入 /tmp 工作區，不污染 repo)
        tools_cfg = _get_tools_config_path()
        if tools_cfg.exists():
            try:
                cfg_data = json.loads(tools_cfg.read_text(encoding="utf-8"))
                g_cfg = cfg_data.setdefault("gitea", {})
                g_cfg["url"] = base_url.strip()
                g_cfg["owner"] = org_name
                g_repos = g_cfg.setdefault("repos", {})
                g_repos["workflows"] = f"{repo_prefix}-workflows"
                g_repos["configs"] = f"{repo_prefix}-configs"
                g_repos["secrets"] = f"{repo_prefix}-secrets"
                tools_cfg.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

        return True, ci_token

    return False, "Failed to provision token"


def provision_gitea_master_token(base_url, auth_str, gitea_user, org_name, repo_prefix):
    """
    為 Gitea 管理員帳號簽發最高權限 MASTER_TOKEN，並登記至組織層級 Actions Secrets。
    依據 [docs/security/action-secrets-spec.md] 規範，嚴禁落地本機。
    """
    # 透過 GET /api/v1/user 解析真實 username，避免使用者輸入 email (如 labadmin@domain.com) 導致 /users/{email}/tokens 404
    actual_username = gitea_user
    try:
        user_req = urllib.request.Request(
            f"{base_url}/api/v1/user",
            headers={
                "Authorization": f"Basic {auth_str}",
                "User-Agent": "OpenLabOps-Init"
            }
        )
        with urllib.request.urlopen(user_req, timeout=5) as resp:
            if resp.status == 200:
                u_data = json.loads(resp.read().decode("utf-8"))
                actual_username = u_data.get("username", u_data.get("login", gitea_user))
    except Exception:
        pass

    token_name = f"{repo_prefix}-master-token-{int(time.time())}"
    token_payload = json.dumps({
        "name": token_name,
        "scopes": ["all"]
    }).encode("utf-8")

    master_token = ""
    req = urllib.request.Request(
        f"{base_url}/api/v1/users/{actual_username}/tokens",
        data=token_payload,
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "User-Agent": "OpenLabOps-Init"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                data = json.loads(resp.read().decode("utf-8"))
                master_token = data.get("sha1", data.get("token", ""))
    except Exception as e:
        return False, str(e)

    if master_token:
        # 1. 登記 MASTER_TOKEN
        secret_payload = json.dumps({"data": master_token}).encode("utf-8")
        secret_req = urllib.request.Request(
            f"{base_url}/api/v1/orgs/{org_name}/actions/secrets/MASTER_TOKEN",
            data=secret_payload,
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "User-Agent": "OpenLabOps-Init"
            },
            method="PUT"
        )
        try:
            with urllib.request.urlopen(secret_req, timeout=5) as resp:
                pass
        except Exception:
            pass

        # 2. 登記 GITEA_HOST 與 ORG_NAME 供 Actions 流程自我定位
        parsed_b = urllib.parse.urlparse(base_url)
        ghost = parsed_b.netloc or parsed_b.hostname or "gitea.lab"

        for var_k, var_v in [("GITEA_HOST", ghost), ("ORG_NAME", org_name)]:
            v_payload = json.dumps({"data": var_v}).encode("utf-8")
            # 登記至 Secrets
            s_req = urllib.request.Request(
                f"{base_url}/api/v1/orgs/{org_name}/actions/secrets/{var_k}",
                data=v_payload,
                headers={"Authorization": f"Basic {auth_str}", "Content-Type": "application/json", "User-Agent": "OpenLabOps-Init"},
                method="PUT"
            )
            try:
                with urllib.request.urlopen(s_req, timeout=5): pass
            except Exception: pass
            # 登記至 Variables
            var_req = urllib.request.Request(
                f"{base_url}/api/v1/orgs/{org_name}/actions/variables/{var_k}",
                data=json.dumps({"value": var_v}).encode("utf-8"),
                headers={"Authorization": f"Basic {auth_str}", "Content-Type": "application/json", "User-Agent": "OpenLabOps-Init"},
                method="PUT"
            )
            try:
                with urllib.request.urlopen(var_req, timeout=5): pass
            except Exception: pass

        return True, "MASTER_TOKEN registered"

    return False, "Failed to generate master token"


def provision_gitea_federation_repos(gitea_url, gitea_user, gitea_password, org_name, repo_prefix):
    """
    透過 Gitea REST API 在指定組織下自動建立 5 大下游聯邦倉庫 (ansible, configs, secrets, tools, workflows)。
    嚴格綁定組織層級 [INV-03]，100% Python 3 標準庫 [INV-01]，冪等安全。
    """
    auth_str = base64.b64encode(f"{gitea_user}:{gitea_password}".encode("utf-8")).decode("ascii")
    base_url = gitea_url.rstrip("/")
    created_repos = []

    # 1. 確保組織存在
    org_ok, org_msg = ensure_gitea_organization(base_url, auth_str, org_name)
    print(f"  • Ensuring Gitea Organization '{org_name}'... [{org_msg}]")

    # 2. 自動建立 5 大聯邦倉庫於組織底下
    for r_type in FEDERATION_REPO_TYPES:
        repo_name = f"{repo_prefix}-{r_type}"
        payload = json.dumps({
            "name": repo_name,
            "private": True,
            "description": f"OpenLabOps Federation Component: {r_type.upper()}",
            "auto_init": False
        }).encode("utf-8")

        ep = f"{base_url}/api/v1/orgs/{org_name}/repos"
        req = urllib.request.Request(
            ep,
            data=payload,
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "User-Agent": "OpenLabOps-Init"
            },
            method="POST"
        )
        repo_status = None
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    repo_status = f"{org_name}/{repo_name} (Created)"
        except urllib.error.HTTPError as e:
            if e.code == 409:
                repo_status = f"{org_name}/{repo_name} (Already Exists)"
            else:
                repo_status = f"{org_name}/{repo_name} (HTTP {e.code})"
        except Exception as e:
            repo_status = f"{org_name}/{repo_name} (Error: {e})"

        created_repos.append(repo_status or f"{org_name}/{repo_name} (Pending)")

    # 3. 自動配置 ci-bot 與本機 .gitea_token (外部 CLI 觸發專用)
    bot_ok, bot_token = provision_gitea_ci_bot(base_url, auth_str, gitea_user, gitea_password, org_name, repo_prefix)
    if bot_ok:
        print(f"\n  {C_BOLD}{C_GREEN}╔══════════════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"  {C_BOLD}{C_GREEN}║              🔑 GITEA AUTOMATION TOKEN ISSUED (ci-bot)               ║{C_RESET}")
        print(f"  {C_BOLD}{C_GREEN}╠══════════════════════════════════════════════════════════════════════╣{C_RESET}")
        print(f"  ║ {C_CYAN}Robot User{C_RESET}     : ci-bot")
        _masked_tok = (bot_token[:6] + "..." + bot_token[-4:]) if len(bot_token) > 12 else "***"
        print(f"  ║ {C_CYAN}Token{C_RESET}          : {C_BOLD}{C_YELLOW}{_masked_tok}{C_RESET}")
        print(f"  ║ {C_CYAN}Token File{C_RESET}     : /usr/local/bin/{repo_prefix}/.gitea_token (mode 0600)")
        print(f"  ║ {C_CYAN}Scope & Role{C_RESET}   : External CLI Trigger (Non-Action-Secret)")
        print(f"  {C_BOLD}{C_GREEN}╚══════════════════════════════════════════════════════════════════════╝{C_RESET}\n")
    else:
        print(f"  • Provisioning Gitea Robot Account 'ci-bot'... {C_YELLOW}[!] Warning: {bot_token}{C_RESET}")

    # 4. 自動為管理員簽發全權限 MASTER_TOKEN 並登記至 Org Secrets (不落地本機)
    master_ok, master_msg = provision_gitea_master_token(base_url, auth_str, gitea_user, org_name, repo_prefix)
    if master_ok:
        print(f"  • Registering Gitea Admin 'MASTER_TOKEN' to Actions Secrets... {C_GREEN}[✓] Registered ({org_name}){C_RESET}")
    else:
        print(f"  • Registering Gitea Admin 'MASTER_TOKEN' to Actions Secrets... {C_YELLOW}[!] Note: {master_msg}{C_RESET}")

    # 5. 設定 Org Actions Variables (GIT_HOST, ORG_NAME) 避免工作流硬編碼
    gitea_host_val = base_url.replace("http://", "").replace("https://", "").rstrip("/")
    for var_name, var_val in [("GIT_HOST", gitea_host_val), ("ORG_NAME", org_name)]:
        var_url = f"{base_url}/api/v1/orgs/{org_name}/actions/variables/{var_name}"
        var_payload = json.dumps({"name": var_name, "value": var_val}).encode("utf-8")
        for method in ("PUT", "POST"):
            try:
                vreq = urllib.request.Request(
                    var_url,
                    data=var_payload,
                    headers={
                        "Authorization": f"Basic {auth_str}",
                        "Content-Type": "application/json",
                        "User-Agent": "OpenLabOps-Init"
                    },
                    method=method
                )
                with urllib.request.urlopen(vreq, timeout=5) as resp:
                    if resp.status in (200, 201, 204):
                        break
            except urllib.error.HTTPError as he:
                if he.code in (400, 404, 409) and method == "PUT":
                    continue
                break
            except Exception:
                break

    return created_repos, (bot_token if bot_ok else None)


def push_federation_baselines_to_gitea(cluster_config, org_name, repo_prefix):
    """
    透過本機 OpenSSH 環境將各聯邦組件之正式基線直接 Git Push 至 Gitea 組織倉庫。
    達成：
    1. Gitea 遠端倉庫即時具備完整代碼 (非空倉庫)。
    2. 本機完全無需手動 git clone 5 大下游倉庫 [INV-03]。
    3. 本機工作區保持 100% 乾淨，零多餘散落目錄。
    """
    import tempfile
    gitea_url = cluster_config.get("gitea_url", "http://gitea.lab")
    parsed_host = urllib.parse.urlparse(gitea_url).hostname or "gitea.lab"
    gitea_host = cluster_config.get("gitea_host", parsed_host)
    gitea_ssh_port = str(cluster_config.get("gitea_ssh_port", 22))

    print(f"\n  • Pushing Initial Federation Baselines directly to Gitea ({org_name}/{repo_prefix}-*)...")

    components = {
        "operations": [
            ("ansible", "ansible"),
            ("tools", "tools"),
            ("bin", "bin"),
            ("engine", "engine"),
            ("schema", "schema"),
            ("conf", "conf"),
            ("lang", "lang"),
        ],
        "workflows": [
            ("workflows/.gitea", ".gitea"),
        ],
        "configs": [],
        "secrets": []
    }

    for c_name, mappings in components.items():
        remote_repo = f"{repo_prefix}-{c_name}"
        if gitea_ssh_port != "22":
            remote_url = f"ssh://git@{gitea_host}:{gitea_ssh_port}/{org_name}/{remote_repo}.git"
        else:
            remote_url = f"git@{gitea_host}:{org_name}/{remote_repo}.git"

        parsed_u = urllib.parse.urlparse(gitea_url)
        if cluster_config.get("gitea_user") and cluster_config.get("gitea_password"):
            user = cluster_config["gitea_user"]
            pw = cluster_config["gitea_password"]
            auth_http_url = f"{parsed_u.scheme}://{user}:{pw}@{parsed_u.netloc}/{org_name}/{remote_repo}.git"
        else:
            auth_http_url = f"{gitea_url.rstrip('/')}/{org_name}/{remote_repo}.git"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            for src_rel, dest_rel in mappings:
                src_path = OPS_DIR / src_rel
                dest_path = tmp_path / dest_rel
                if src_path.exists():
                    if src_path.is_dir():
                        shutil.copytree(src_path, dest_path, dirs_exist_ok=True, ignore_dangling_symlinks=True)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dest_path)

            # 確保 README.md 存在 (configs 與 secrets 初次建立時為乾淨空白倉庫)
            readme = tmp_path / "README.md"
            if not readme.exists():
                readme.write_text(f"# {cluster_config.get('cluster_name', 'OpenLabOps')} Federation: {c_name.upper()}\n\nProduction federation component managed by OpenLabOps Master Operations Hub.\n", encoding="utf-8")

            # Git commit and push
            try:
                subprocess.run(["git", "init", "-b", "main"], cwd=tmp_dir, capture_output=True, check=True)
                admin_u = cluster_config.get("admin_user", "admin")
                domain_h = cluster_config.get("domain", "local")
                c_display = cluster_config.get('cluster_name', 'OpenLab')
                subprocess.run(["git", "config", "user.name", f"{c_display} Master"], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "config", "user.email", f"{admin_u}@{domain_h}.local"], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "commit", "-m", f"chore(federation): initialize {remote_repo} production baseline"], cwd=tmp_dir, capture_output=True, check=True)

                p_res = subprocess.run(
                    ["git", "push", remote_url, "main:main", "--force"],
                    cwd=tmp_dir, capture_output=True, text=True, timeout=20
                )
                if p_res.returncode != 0:
                    p_res = subprocess.run(
                        ["git", "push", auth_http_url, "main:main", "--force"],
                        cwd=tmp_dir, capture_output=True, text=True, timeout=20
                    )
                if p_res.returncode == 0:
                    print(f"    {C_GREEN}[✓] Baseline Pushed -> {org_name}/{remote_repo} (main){C_RESET}")
                else:
                    print(f"    {C_YELLOW}[!] Push to {remote_repo} note: {p_res.stderr.strip()}{C_RESET}")
            except Exception as e:
                print(f"    {C_YELLOW}[!] Push to {remote_repo} failed: {e}{C_RESET}")


def push_fresh_configs_and_secrets_to_gitea(cluster_config, org_name, repo_prefix="openlab"):
    """
    Day-0 初次執行後，將本次探測產生的全新地面事實 (node-information) 與安全公鑰 (secrets) 推送到 Gitea。
    初次跑完產生乾淨的 v1 版本，完全由 lab-init 運行產生，不依賴舊備份。
    """
    gitea_url = cluster_config.get("gitea_url", "http://gitea.lab:3000")
    parsed_u = urllib.parse.urlparse(gitea_url)
    gitea_host = parsed_u.hostname or "gitea.lab"
    gitea_ssh_port = str(cluster_config.get("gitea_ssh_port", "22"))

    cluster_name = cluster_config.get("cluster_name", "OpenLabOps")

    compiled_tmp_obj = tempfile.TemporaryDirectory()
    compiled_base = Path(compiled_tmp_obj.name)
    wd = _get_work_dir()
    manifest_cand = (wd / "conf" / f"{repo_prefix}.manifest.yml") if wd else (OPS_DIR / "conf" / f"{repo_prefix}.manifest.yml")
    if not manifest_cand.exists():
        manifest_cand = OPS_DIR / "conf" / f"{repo_prefix}.manifest.yml"
    if not manifest_cand.exists():
        manifest_cand = OPS_DIR / "conf" / "openlab.manifest.yml"
    if manifest_cand.exists() and (OPS_DIR / "engine" / "compiler.py").exists():
        subprocess.run(
            [
                sys.executable, str(OPS_DIR / "engine" / "compiler.py"),
                "--manifest", str(manifest_cand),
                "--apply", "--create-dest-dirs",
                "--base-dir", str(compiled_base),
                "--dest-prefix", f"{repo_prefix}-",
            ],
            cwd=str(OPS_DIR),
            capture_output=True,
            text=True,
        )

    repos_to_push = ["configs", "secrets"]
    for c_name in repos_to_push:
        remote_repo = f"{repo_prefix}-{c_name}"
        if gitea_ssh_port != "22":
            remote_url = f"ssh://git@{gitea_host}:{gitea_ssh_port}/{org_name}/{remote_repo}.git"
        else:
            remote_url = f"git@{gitea_host}:{org_name}/{remote_repo}.git"

        if cluster_config.get("gitea_user") and cluster_config.get("gitea_password"):
            user = cluster_config["gitea_user"]
            pw = cluster_config["gitea_password"]
            auth_http_url = f"{parsed_u.scheme}://{user}:{pw}@{parsed_u.netloc}/{org_name}/{remote_repo}.git"
        else:
            auth_http_url = f"{gitea_url.rstrip('/')}/{org_name}/{remote_repo}.git"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            if c_name == "configs":
                # 1. 寫入 README.md
                readme = tmp_path / "README.md"
                readme.write_text(
                    f"# {cluster_name} Sensory Ground Truth & Configuration CMDB\n\n"
                    f"Live audited node telemetry facts and declarative configuration baseline.\n"
                    f"Generated on-the-fly by {cluster_name} Master Operations Engine.\n",
                    encoding="utf-8"
                )

                # 2. 注入探測產生的全新 node-information
                node_info_dir = tmp_path / "node-information"
                node_info_dir.mkdir(parents=True, exist_ok=True)
                nodes_dir = _get_nodes_dir()
                if nodes_dir.exists():
                    for nf in sorted(nodes_dir.glob("*.json")):
                        if nf.name in ("current.json", "archive") or nf.name.startswith("."):
                            continue
                        hname = nf.stem[5:] if nf.stem.startswith("node_") else nf.stem
                        shutil.copy2(nf, node_info_dir / f"node_{hname}.json")

                # 3. 注入 conf 與 schema (若有 /tmp 工作區產出之站點 manifest，一併覆蓋注入)
                conf_dest = tmp_path / "conf"
                conf_dest.mkdir(parents=True, exist_ok=True)
                if (OPS_DIR / "conf").exists():
                    for f in (OPS_DIR / "conf").iterdir():
                        if f.is_file() and f.suffix in (".yml", ".yaml", ".json"):
                            shutil.copy2(f, conf_dest / f.name)
                if wd and (wd / "conf").exists():
                    for f in (wd / "conf").iterdir():
                        if f.is_file() and f.suffix in (".yml", ".yaml", ".json"):
                            shutil.copy2(f, conf_dest / f.name)

                if (OPS_DIR / "schema").exists():
                    shutil.copytree(OPS_DIR / "schema", tmp_path / "schema", dirs_exist_ok=True)

                if (OPS_DIR / "AGENTS.md").exists():
                    shutil.copy2(OPS_DIR / "AGENTS.md", tmp_path / "AGENTS.md")

                compiled_cfg_dir = compiled_base / f"{repo_prefix}-configs"
                if compiled_cfg_dir.exists():
                    for sub in ("ssh-config", "conf"):
                        if (compiled_cfg_dir / sub).exists():
                            shutil.copytree(compiled_cfg_dir / sub, tmp_path / sub, dirs_exist_ok=True)

                commit_msg = "feat(cmdb): push freshly discovered node telemetry facts (v1)"

            elif c_name == "secrets":
                # 1. 寫入 README.md
                readme = tmp_path / "README.md"
                readme.write_text(
                    f"# {cluster_name} Secrets & SSH Key Store\n\n"
                    f"Zero-Trust SSH managed keys (private keys *.key and public keys *.pub) and endpoint access configurations.\n"
                    f"Centralized key vault for Ansible automation and cluster node management.\n",
                    encoding="utf-8"
                )

                # 2. 收集受控金鑰對 (*.key 私鑰與 *.pub 公鑰) 供 Ansible 與節點自動化使用
                ssh_key_dir = tmp_path / "ssh-key"
                ssh_key_dir.mkdir(parents=True, exist_ok=True)
                ssh_dir = Path.home() / ".ssh"
                if ssh_dir.exists():
                    for kf in sorted(list(ssh_dir.glob("*.key")) + list(ssh_dir.glob("*.pub"))):
                        shutil.copy2(kf, ssh_key_dir / kf.name)

                # 3. 收集端點與集群 SSH 連線設定 (ssh-config/config)
                ssh_cfg_dir = tmp_path / "ssh-config"
                ssh_cfg_dir.mkdir(parents=True, exist_ok=True)
                candidate_configs = [
                    compiled_base / f"{repo_prefix}-secrets" / "ssh-config" / "config",
                    compiled_base / f"{repo_prefix}-configs" / "ssh-config" / "openlab" / "config",
                    compiled_base / f"{repo_prefix}-configs" / "ssh-config" / "config",
                    OPS_DIR.parent / f"{repo_prefix}-secrets" / "ssh-config" / "config",
                    OPS_DIR.parent / f"{repo_prefix}-configs" / "ssh-config" / "openlab" / "config",
                    OPS_DIR.parent / f"{repo_prefix}-configs" / "ssh-config" / "config",
                ]
                for cc in candidate_configs:
                    if cc.exists():
                        shutil.copy2(cc, ssh_cfg_dir / "config")
                        break

                # 4. 注入安全架構說明文件
                if (OPS_DIR / "docs" / "security").exists():
                    shutil.copytree(OPS_DIR / "docs" / "security", tmp_path / "docs" / "security", dirs_exist_ok=True)

                commit_msg = "feat(secrets): push initial public keys and ssh config (v1)"

            # Git commit and push
            try:
                subprocess.run(["git", "init", "-b", "main"], cwd=tmp_dir, capture_output=True, check=True)
                admin_u = cluster_config.get("admin_user", "admin")
                domain_h = cluster_config.get("domain", "local")
                c_display = cluster_config.get('cluster_name', 'OpenLab')
                subprocess.run(["git", "config", "user.name", f"{c_display} Master"], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "config", "user.email", f"{admin_u}@{domain_h}.local"], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=True)
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=tmp_dir, capture_output=True, check=True)

                p_res = subprocess.run(
                    ["git", "push", remote_url, "main:main", "--force"],
                    cwd=tmp_dir, capture_output=True, text=True, timeout=20
                )
                if p_res.returncode != 0:
                    p_res = subprocess.run(
                        ["git", "push", auth_http_url, "main:main", "--force"],
                        cwd=tmp_dir, capture_output=True, text=True, timeout=20
                    )
                if p_res.returncode == 0:
                    print(f"    {C_GREEN}[✓] Fresh State Pushed -> {org_name}/{remote_repo} (main){C_RESET}")
                else:
                    print(f"    {C_YELLOW}[!] Push to {remote_repo} note: {p_res.stderr.strip()}{C_RESET}")
            except Exception as e:
                print(f"    {C_YELLOW}[!] Push to {remote_repo} failed: {e}{C_RESET}")


def deploy_ops_tools_and_configs(cluster_config, repo_prefix="openlab", target_hosts=None):
    """
    呼叫正式生產劇本 (deploy-ops-tools.yml) 部署維運工具鏈至目標節點。
    完全遵循 [INV-09] 生產工具標準。
    """
    playbook = OPS_DIR / "ansible" / "playbooks" / "deploy-ops-tools.yml"
    target = target_hosts or os.environ.get("LAB_TARGET_HOSTS", "localhost")
    ansible_u = cluster_config.get("ansible_user", "lab")
    ssh_home = Path(os.environ.get("LAB_SSH_HOME", str(Path.home() / ".ssh")))
    priv_key = ssh_home / f"{ansible_u}.key"
    target_loc = cluster_config.get("lang", "en_US" if "openlab" in OPS_DIR.name.lower() else "zh_TW")

    if target in ("localhost", "127.0.0.1"):
        cmd = [
            "ansible-playbook",
            "-i", "localhost,",
            "-c", "local",
            str(playbook),
            "-e", f"repo_prefix={repo_prefix}",
            "-e", f"ops_tools_install_dir=/usr/local/bin/{repo_prefix}",
            "-e", "target_hosts=localhost",
            "-e", f"target_locale={target_loc}"
        ]
    else:
        inv_file = _get_inventory_dir() / "hosts.yml"
        if not inv_file.exists():
            inv_file = OPS_DIR / "ansible" / "inventory" / "hosts.yml"
        if not inv_file.exists():
            inv_file = OPS_DIR.parent / f"{repo_prefix}-ansible" / "inventory" / "hosts.yml"
        cmd = [
            "ansible-playbook",
            "-i", str(inv_file) if inv_file.exists() else "localhost,",
            str(playbook),
            "-e", f"repo_prefix={repo_prefix}",
            "-e", f"ops_tools_install_dir=/usr/local/bin/{repo_prefix}",
            "-e", f"target_hosts={target}",
            "-e", f"target_locale={target_loc}"
        ]
        if priv_key.exists():
            cmd.extend(["-u", ansible_u, "--private-key", str(priv_key)])
    res = subprocess.run(cmd, capture_output=True, text=True)

    # 固化本機 tools.config.json 與全域環境變數語系設定 (寫入 /tmp 工作區，不污染 repo)
    tools_cfg_file = _get_tools_config_path()
    if tools_cfg_file.exists():
        try:
            cfg_data = json.loads(tools_cfg_file.read_text(encoding="utf-8"))
            cfg_data["default_locale"] = target_loc
            tools_cfg_file.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

    # 固化獨立 locale 狀態檔至 ~/.config/<prefix>/locale 與 /usr/local/etc/<prefix>/locale
    for loc_p in [
        Path.home() / ".config" / repo_prefix / "locale",
        Path.home() / ".config" / "openlab" / "locale",
        Path.home() / ".config" / "openlab" / "locale",
        Path(f"/usr/local/etc/{repo_prefix}/locale"),
    ]:
        try:
            loc_p.parent.mkdir(parents=True, exist_ok=True)
            loc_p.write_text(f"{target_loc}\n", encoding="utf-8")
        except Exception:
            pass

    # 固化環境變數至 ~/.bashrc 與 ~/.zshrc (支援複寫更新舊語系)
    import re
    for shrc_p in [Path.home() / ".bashrc", Path.home() / ".zshrc"]:
        if shrc_p.exists():
            try:
                s_txt = shrc_p.read_text(encoding="utf-8")
                if "export LAB_LANG=" in s_txt:
                    s_txt = re.sub(r'export LAB_LANG="?[^"\n]+"?', f'export LAB_LANG="{target_loc}"', s_txt)
                else:
                    s_txt += f'\nexport LAB_LANG="{target_loc}"\n'
                if "export LAB_LANG=" in s_txt:
                    s_txt = re.sub(r'export LAB_LANG="?[^"\n]+"?', f'export LAB_LANG="{target_loc}"', s_txt)
                else:
                    s_txt += f'export LAB_LANG="{target_loc}"\n'
                shrc_p.write_text(s_txt, encoding="utf-8")
            except Exception:
                pass

    # 嘗試固化至 /etc/environment
    try:
        env_f = Path("/etc/environment")
        if env_f.exists() and os.access(str(env_f), os.W_OK):
            e_txt = env_f.read_text(encoding="utf-8")
            if "LAB_LANG=" in e_txt:
                e_txt = re.sub(r'LAB_LANG="?[^"\n]+"?', f'LAB_LANG="{target_loc}"', e_txt)
            else:
                e_txt += f'\nLAB_LANG="{target_loc}"\n'
            if "LAB_LANG=" in e_txt:
                e_txt = re.sub(r'LAB_LANG="?[^"\n]+"?', f'LAB_LANG="{target_loc}"', e_txt)
            else:
                e_txt += f'LAB_LANG="{target_loc}"\n'
            env_f.write_text(e_txt, encoding="utf-8")
    except Exception:
        pass

    # 即時同步當前進程環境
    os.environ["LAB_LANG"] = target_loc
    os.environ["LAB_LANG"] = target_loc

    return res.returncode == 0, res.stdout or res.stderr


def provision_github_secret_to_gitea(gitea_url, gitea_user, gitea_password, org_or_user, token):
    """透過 Gitea REST API 將 GH_TOKEN 登記為組織或個人 Action Secret"""
    auth_str = base64.b64encode(f"{gitea_user}:{gitea_password}".encode("utf-8")).decode("ascii")
    payload = json.dumps({"data": token}).encode("utf-8")
    endpoints = [
        f"{gitea_url.rstrip('/')}/api/v1/orgs/{org_or_user}/actions/secrets/GH_TOKEN",
        f"{gitea_url.rstrip('/')}/api/v1/user/actions/secrets/GH_TOKEN"
    ]
    for ep in endpoints:
        req = urllib.request.Request(
            ep,
            data=payload,
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
                "User-Agent": "OpenLabOps-Init"
            },
            method="PUT"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201, 204):
                    return True, ep
        except Exception:
            continue
    return False, "Failed to connect to Gitea Actions Secrets API"


def detect_local_network_context():
    """純標準庫自動探測本機預設網段與 Gateway IP"""
    default_subnet = "192.168.1.0/24"
    default_gw = "192.168.1.1"
    try:
        res = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split()
            if "via" in parts:
                gw_idx = parts.index("via") + 1
                if gw_idx < len(parts):
                    default_gw = parts[gw_idx]
            if "dev" in parts:
                dev_idx = parts.index("dev") + 1
                if dev_idx < len(parts):
                    dev_name = parts[dev_idx]
                    addr_res = subprocess.run(["ip", "-o", "-f", "inet", "addr", "show", dev_name], capture_output=True, text=True, timeout=2)
                    if addr_res.returncode == 0 and addr_res.stdout.strip():
                        for token in addr_res.stdout.split():
                            if "/" in token and not token.startswith("brd"):
                                ip_part, mask_part = token.split("/", 1)
                                octets = ip_part.split(".")
                                if len(octets) == 4 and mask_part == "24":
                                    default_subnet = f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
                                elif len(octets) == 4:
                                    default_subnet = token
                                break
    except Exception:
        pass
    return default_subnet, default_gw


# ──────────────────────────────────────────────────────────────────────────────
# 1. Base Information Setup (Interactive TUI or Declarative Manifest)
# ──────────────────────────────────────────────────────────────────────────────
def setup_base_parameters(manifest_meta=None, non_interactive=False, cli_lang=None):
    """收集基礎叢集參數，支援 TUI 互動提示或 Manifest 預填，並以 i18n 語系貫穿全局"""
    from engine.bsd_dialog import BSDDialog, is_bsd_tui_supported

    # 0. 語系選擇 (Language / Locale Selection)
    chosen_lang = cli_lang or os.getenv("LAB_LANG") or os.getenv("LAB_LANG")
    if manifest_meta and not chosen_lang:
        chosen_lang = manifest_meta.get("lang") or manifest_meta.get("locale")
        if chosen_lang and "." in chosen_lang:
            chosen_lang = chosen_lang.split(".")[0]

    is_openlab = (
        "openlab" in OPS_DIR.name.lower()
        or any("lab-" in arg for arg in sys.argv)
        or os.getenv("LAB_MODE") == "1"
        or (manifest_meta and (
            "openlab" in str(manifest_meta.get("cluster", "")).lower()
            or manifest_meta.get("default_target_user") == "ansible"
            or (isinstance(manifest_meta.get("cluster"), dict) and manifest_meta["cluster"].get("ansible_user") == "ansible")
        ))
    )

    if not chosen_lang:
        if is_openlab and non_interactive:
            chosen_lang = "en_US"
        elif non_interactive:
            chosen_lang = detect_system_locale()
        elif is_bsd_tui_supported():
            lang_dialog = BSDDialog(title="Initialization Wizard", subtitle="Language Selection")
            if is_openlab:
                lang_items = [
                    ("en_US", "English (US) - Standard English"),
                    ("zh_TW", "正體中文 (繁體) - Traditional Chinese"),
                    ("ja_JP", "日本語 - Japanese")
                ]
            else:
                lang_items = [
                    ("zh_TW", "正體中文 (繁體) - Traditional Chinese"),
                    ("en_US", "English (US) - Standard English"),
                    ("ja_JP", "日本語 - Japanese")
                ]
            cur_loc = detect_system_locale()
            sel_lang, _ = lang_dialog.menu(
                "Language Selection / 語言設定",
                "Please select language for setup wizard and tools / 請選擇安裝精靈與工具語系:",
                lang_items,
                default_tag=cur_loc,
                width=72,
                height=14
            )
            chosen_lang = sel_lang or cur_loc
        else:
            print("\n" + "=" * 64)
            print("  Language Selection / 語言選擇 / 言語選択")
            print("=" * 64)
            if is_openlab:
                print("  1) en_US : English (US) [Default]")
                print("  2) zh_TW : 正體中文 (繁體) - Traditional Chinese")
                print("  3) ja_JP : 日本語 - Japanese")
                l_choice = interactive_prompt("Select language (1-3, default 1)", default="1")
                if l_choice == "2" or l_choice.lower().startswith("zh"):
                    chosen_lang = "zh_TW"
                elif l_choice == "3" or l_choice.lower().startswith("ja"):
                    chosen_lang = "ja_JP"
                else:
                    chosen_lang = "en_US"
            else:
                print("  1) zh_TW : 正體中文 (繁體) [預設 / Default]")
                print("  2) en_US : English (US)")
                print("  3) ja_JP : 日本語")
                l_choice = interactive_prompt("請選擇語言 (1-3, 預設 1)", default="1")
                if l_choice == "2" or l_choice.lower().startswith("en"):
                    chosen_lang = "en_US"
                elif l_choice == "3" or l_choice.lower().startswith("ja"):
                    chosen_lang = "ja_JP"
                else:
                    chosen_lang = "zh_TW"

    set_locale(chosen_lang)
    auto_subnet, auto_gw = detect_local_network_context()

    if is_openlab:
        defaults = {
            "lang": chosen_lang or "en_US",
            "locale": f"{chosen_lang or 'en_US'}.UTF-8",
            "cluster_name": "OpenLab",
            "org": "OpenLabOps",
            "domain": "lab",
            "admin_user": os.getenv("USER", "labadmin"),
            "ansible_user": "ansible",
            "flat_lan": auto_subnet,
            "service_lan": auto_subnet,
            "gateway_ip": auto_gw,
            "gitea_url": os.environ.get("GITEA_URL") or "http://gitea.lab:3000",
            "gitea_user": os.getenv("USER", "labadmin"),
            "gitea_password": "labpassword123",
            "repo_prefix": "openlab",
            "github_enabled": False,
            "github_owner": "",
            "github_token": os.getenv("GH_TOKEN", ""),
            "docker_host": "localhost",
            "docker_user": os.getenv("USER", "labadmin"),
            "docker_port": 22
        }
    else:
        defaults = {
            "lang": chosen_lang,
            "locale": f"{chosen_lang}.UTF-8",
            "cluster_name": "OpenLabOps",
            "org": "OpenLabOps",
            "domain": "lab",
            "admin_user": "labadmin",
            "ansible_user": "lab",
            "flat_lan": auto_subnet,
            "service_lan": auto_subnet,
            "gateway_ip": auto_gw,
            "gitea_url": os.environ.get("GITEA_URL") or "http://gitea.lab",
            "gitea_user": "labadmin",
            "gitea_password": "labtest123",
            "repo_prefix": "openlab",
            "github_enabled": False,
            "github_owner": "",
            "github_token": os.getenv("GH_TOKEN", ""),
            "docker_host": "localhost",
            "docker_user": "labadmin",
            "docker_port": 22
        }
    if manifest_meta:
        for k in defaults:
            if k in ("lang", "locale") and chosen_lang:
                continue
            if k in manifest_meta:
                defaults[k] = manifest_meta[k]
        defaults["lang"] = chosen_lang
        defaults["locale"] = f"{chosen_lang}.UTF-8"
        manifest_meta["lang"] = chosen_lang
        manifest_meta["locale"] = f"{chosen_lang}.UTF-8"
        if "cluster" in manifest_meta:
            if isinstance(manifest_meta["cluster"], dict):
                manifest_meta["cluster"]["locale"] = f"{chosen_lang}.UTF-8"
                defaults["cluster_name"] = manifest_meta["cluster"].get("name", defaults["cluster_name"])
                defaults["org"] = manifest_meta["cluster"].get("org", defaults["cluster_name"])
                defaults["domain"] = manifest_meta["cluster"].get("domain", defaults["domain"])
                defaults["admin_user"] = manifest_meta["cluster"].get("admin_user", defaults["admin_user"])
                defaults["ansible_user"] = manifest_meta["cluster"].get("ansible_user", defaults["ansible_user"])
            elif manifest_meta["cluster"]:
                defaults["cluster_name"] = str(manifest_meta["cluster"])
                defaults["org"] = str(manifest_meta.get("org") or manifest_meta["cluster"])
        if manifest_meta.get("org"):
            defaults["org"] = str(manifest_meta["org"])
        if "git_platform" in manifest_meta and isinstance(manifest_meta["git_platform"], dict):
            gp = manifest_meta["git_platform"]
            host = gp.get("host", "gitea.lab")
            port = int(gp.get("http_port", 80))
            defaults["gitea_url"] = f"http://{host}" if port in (80, 443) else f"http://{host}:{port}"
            if "org" in gp:
                defaults["org"] = gp["org"]
            if "repo_prefix" in gp:
                defaults["repo_prefix"] = gp["repo_prefix"]
        elif "gitea_url" in manifest_meta and manifest_meta["gitea_url"]:
            defaults["gitea_url"] = str(manifest_meta["gitea_url"])
        elif "gitea_host" in manifest_meta and manifest_meta["gitea_host"]:
            gh = str(manifest_meta["gitea_host"])
            defaults["gitea_url"] = f"http://{gh}" if not gh.startswith("http") else gh
        if "services" in manifest_meta and isinstance(manifest_meta["services"], dict) and "docker_host" in manifest_meta["services"]:
            dh = manifest_meta["services"]["docker_host"]
            if isinstance(dh, dict):
                defaults["docker_host"] = dh.get("host", "localhost")
                defaults["docker_user"] = dh.get("ssh_user", defaults["admin_user"])
                defaults["docker_port"] = int(dh.get("ssh_port", 22))
            else:
                defaults["docker_host"] = str(dh)
        if "extensions" in manifest_meta and isinstance(manifest_meta["extensions"], dict) and "github" in manifest_meta["extensions"]:
            gh = manifest_meta["extensions"]["github"]
            if isinstance(gh, dict):
                defaults["github_enabled"] = str(gh.get("enabled", "false")).lower() in ("true", "1", "yes")
                defaults["github_owner"] = gh.get("owner", defaults["admin_user"])

        if "networks" in manifest_meta and isinstance(manifest_meta["networks"], dict):
            net = manifest_meta["networks"]
            defaults["flat_lan"] = net.get("flat_lan") or net.get("service_lan") or defaults["flat_lan"]
            defaults["service_lan"] = net.get("service_lan") or defaults["flat_lan"]
            defaults["gateway_ip"] = net.get("gateway_ip") or defaults["gateway_ip"]

    if non_interactive:
        print(f"  • Language / Locale: {C_GREEN}{defaults['lang']} ({defaults['locale']}){C_RESET}")
        print(f"  • Cluster Name     : {C_GREEN}{defaults['cluster_name']}{C_RESET}")
        print(f"  • Domain           : {C_GREEN}{defaults['domain']}{C_RESET}")
        print(f"  • Network Subnet   : {C_GREEN}{defaults['flat_lan']} (GW: {defaults['gateway_ip']}){C_RESET}")
        print(f"  • Admin User       : {C_GREEN}{defaults['admin_user']}{C_RESET}")
        print(f"  • Ansible User     : {C_GREEN}{defaults['ansible_user']}{C_RESET}")
        print(f"  • Gitea Endpoint   : {C_GREEN}{defaults['gitea_url']}{C_RESET}")
        print(f"  • Docker Host      : {C_GREEN}{defaults['docker_host']}{C_RESET}")
        if defaults["github_enabled"]:
            print(f"  • GitHub Linked    : {C_GREEN}Yes (Owner: {defaults['github_owner']}){C_RESET}")
        else:
            print(f"  • GitHub Linked    : {C_DIM}No (Air-Gapped Flat LAN Mode){C_RESET}")
        return defaults

    # ──────────────────────────────────────────────────────────────────────────
    # 分支 A: bsdinstall 典雅 Curses 藍底對話方塊介面 (Interactive TUI)
    # ──────────────────────────────────────────────────────────────────────────
    if is_bsd_tui_supported():
        dialog = BSDDialog(title=f"{defaults['cluster_name']} Operations Engine", subtitle="Day-0 Initial Setup Wizard")

        # 歡迎畫面
        dialog.msgbox(
            t("init.welcome_title", "Day-0 Initial Setup Wizard"),
            t("init.welcome_desc", "Zero External Dependencies | 100% Native Production Suite\n\n歡迎使用 Day-0 初始化引導精靈。\n本精靈將引導您配置叢集基本參數、自架容器服務、納管節點與金鑰安全防護。"),
            width=70,
            height=16
        )

        # 步驟 1: 叢集基本身份
        form1_fields = [
            {"key": "cluster_name", "label": t("init.cluster_name_label", "Cluster Name:"), "value": defaults["cluster_name"], "help": t("init.cluster_name_help", "叢集識別名稱")},
            {"key": "domain", "label": t("init.domain_label", "Internal Domain:"), "value": defaults["domain"], "help": t("init.domain_help", "內部解析網域")},
            {"key": "admin_user", "label": t("init.admin_user_label", "Admin User:"), "value": defaults["admin_user"], "help": t("init.admin_user_help", "系統管理員主帳號")},
            {"key": "ansible_user", "label": t("init.ansible_user_label", "Ansible User:"), "value": defaults["ansible_user"], "help": t("init.ansible_user_help", "自動化運維專用帳號")},
        ]
        vals1, btn1 = dialog.form(
            t("init.step1_title", "Step 1/5: Cluster Identity & Core Users"),
            t("init.step1_prompt", "請確認或修改叢集核心識別參數:"),
            form1_fields,
            width=72,
            height=16
        )
        if vals1:
            for k in ("cluster_name", "domain", "admin_user", "ansible_user"):
                if vals1.get(k):
                    defaults[k] = vals1[k]

        # 步驟 2: 容器化服務自動建立 (打X勾選)
        cs_items = [
            {
                "id": "gitea_auto_provision",
                "name": "Gitea Server",
                "label": t("init.service_gitea_label", "Gitea Server - 自架 Git 版本控制平台容器"),
                "desc": t("init.service_gitea_desc", "由精靈自動建立獨立 Gitea 容器 (已有現成實例請勿勾選)"),
                "checked": defaults.get("gitea_auto_provision", False)
            },
            {
                "id": "with_gitea_runner",
                "name": "Gitea Act Runner",
                "label": t("init.service_runner_label", "Gitea Act Runner - CI/CD 自動化工作流執行容器"),
                "desc": t("init.service_runner_desc", "由精靈自動在 Docker 宿主機拉起 Gitea Actions 輕量 Runner"),
                "checked": defaults.get("with_gitea_runner", False)
            },
            {
                "id": "with_agy_remote",
                "name": "AGY-Remote",
                "label": t("init.service_agy_label", "AGY-Remote - AI SRE 運維助理容器"),
                "desc": t("init.service_agy_desc", "由精靈自動建立 AGY-Remote AI 運維輔助容器"),
                "checked": defaults.get("with_agy_remote", False)
            }
        ]
        selected_cs, btn_cs = dialog.checklist(
            t("init.step2_title", "Step 2/5: Container Services Auto-Provisioning"),
            t("init.step2_prompt", "請按 [Space] 打 [X] 勾選需要由專案自動建立的容器服務:\n(若均不需自動建立，直接按 <OK> 即可跳過 Docker Host 設定)"),
            cs_items,
            buttons=[t("common.confirm", "OK"), t("common.skip_all", "Skip All")],
            width=76,
            height=18
        )
        selected_cs = selected_cs or []
        gitea_auto = "gitea_auto_provision" in selected_cs
        runner_auto = "with_gitea_runner" in selected_cs
        agy_auto = "with_agy_remote" in selected_cs
        needs_docker = gitea_auto or runner_auto or agy_auto

        config = dict(defaults)
        config["gitea_auto_provision"] = gitea_auto
        config["with_gitea_runner"] = runner_auto
        config["with_agy_remote"] = agy_auto

        # 步驟 3: Docker 主機設定 (選完需要才會跳出，不需要時跳過)
        if needs_docker:
            form_docker_fields = [
                {"key": "docker_host", "label": t("init.docker_host_label", "Docker Host:"), "value": defaults["docker_host"], "help": t("init.docker_host_help", "輸入 'localhost' 或遠端伺服器 IP")},
                {"key": "docker_user", "label": t("init.docker_user_label", "SSH User:"), "value": defaults["docker_user"], "help": t("init.docker_user_help", "Docker 主機 SSH 登入帳號")},
                {"key": "docker_port", "label": t("init.docker_port_label", "SSH Port:"), "value": str(defaults["docker_port"]), "help": t("init.docker_port_help", "Docker 主機 SSH 端口 (預設 22)")},
            ]
            vals_d, btn_d = dialog.form(
                t("init.step3_title", "Step 3/5: Docker Host Configuration"),
                t("init.step3_prompt", "已勾選自動建立容器服務，請設定 Docker 運行宿主機:"),
                form_docker_fields,
                width=72,
                height=16
            )
            if vals_d:
                config["docker_host"] = vals_d.get("docker_host") or "localhost"
                config["docker_user"] = vals_d.get("docker_user") or defaults["admin_user"]
                try:
                    config["docker_port"] = int(vals_d.get("docker_port", 22))
                except ValueError:
                    config["docker_port"] = 22
        else:
            # 不需要的時候跳過 Docker Host 設定
            config["docker_host"] = "localhost"
            config["docker_user"] = defaults["admin_user"]
            config["docker_port"] = defaults["docker_port"]

        # 步驟 4: Gitea 版本控制平台設定
        gitea_prompt = (
            t("init.step4_prompt_auto", "您已勾選自動建立 Gitea 容器，請設定其初始化帳密與端點:")
            if gitea_auto
            else t("init.step4_prompt_exist", "請設定現有運行中之 Gitea 服務端點與連線帳密:")
        )
        form_gitea_fields = [
            {"key": "gitea_url", "label": t("init.gitea_url_label", "Gitea URL:"), "value": defaults["gitea_url"], "help": t("init.gitea_url_help", "Gitea 服務端點 (如 http://gitea.lab)")},
            {"key": "org", "label": t("init.gitea_org_label", "Organization:"), "value": defaults.get("org", config["cluster_name"]), "help": t("init.gitea_org_help", "Gitea 組織名稱 (如 OpenLabOps)")},
            {"key": "gitea_user", "label": t("init.gitea_user_label", "Admin User:"), "value": defaults["gitea_user"], "help": t("init.gitea_user_help", "Gitea 管理員帳號")},
            {"key": "gitea_password", "label": t("init.gitea_pass_label", "Admin Password:"), "value": defaults["gitea_password"], "secret": True, "help": t("init.gitea_pass_help", "Gitea 管理員密碼")},
            {"key": "repo_prefix", "label": t("init.repo_prefix_label", "Repo Prefix:"), "value": defaults["repo_prefix"], "help": t("init.repo_prefix_help", "倉庫命名前綴 (如 openlab)")},
        ]
        vals_g, btn_g = dialog.form(t("init.step4_title", "Step 4/5: Gitea Platform Setup"), gitea_prompt, form_gitea_fields, width=74, height=18)
        if vals_g:
            for k, v in vals_g.items():
                if v: config[k] = v

        # 步驟 5: 外部 GitHub 平台擴充
        enable_gh = dialog.yesno(
            t("init.step5_title", "Step 5/5: External Platform Extensions"),
            t("init.step5_prompt", "是否關聯/納管外部 GitHub 平台？\n\n• 若選擇 <Yes>，將可設定 GitHub PAT Token 並自動同步 Actions Secrets\n• 若選擇 <No>，系統將以純內網 (Air-Gapped Flat LAN) 模式運行"),
            width=70,
            height=14,
            default=defaults.get("github_enabled", False)
        )
        config["github_enabled"] = enable_gh
        if enable_gh:
            form_gh_fields = [
                {"key": "github_owner", "label": t("init.github_owner_label", "GitHub Owner:"), "value": defaults.get("github_owner") or config["admin_user"], "help": t("init.github_owner_help", "GitHub 帳號或組織名稱")},
                {"key": "github_token", "label": t("init.github_token_label", "GitHub PAT Token:"), "value": defaults.get("github_token", ""), "secret": True, "help": t("init.github_token_help", "需具備 admin:public_key 最小權限")},
            ]
            vals_gh, btn_gh = dialog.form(t("init.step5_title", "GitHub Platform Federation"), t("init.step5_prompt", "請設定 GitHub 帳號與存取憑證:"), form_gh_fields, width=72, height=15)
            if vals_gh:
                config["github_owner"] = vals_gh.get("github_owner", config["admin_user"])
                config["github_token"] = vals_gh.get("github_token", "")
        else:
            config["github_owner"] = ""
            config["github_token"] = ""

        return config

    # ──────────────────────────────────────────────────────────────────────────
    # 分支 B: 經典命令列終端互動介面 (CLI Fallback Mode)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"{C_BOLD}請輸入或確認叢集核心參數 (直接按 Enter 採用預設值):{C_RESET}")
    config = dict(defaults)
    # 1. 叢集基本身份
    config["cluster_name"] = interactive_prompt("叢集識別名稱 (Cluster Name)", default=defaults["cluster_name"])
    config["domain"] = interactive_prompt("內部解析網域 (Domain)", default=defaults["domain"])
    config["admin_user"] = interactive_prompt("系統管理員主帳號 (Admin User)", default=defaults["admin_user"])
    config["ansible_user"] = interactive_prompt("自動化運維專用帳號 (Ansible User)", default=defaults["ansible_user"])

    # 2. 選配容器化服務自動建立 (打X/Y選擇是否由專案自動建立)
    print(f"\n{C_BOLD}選配容器化服務自動建立 (Container Services Auto-Provisioning):{C_RESET}")
    print(f"  {C_DIM}請選擇是否需要由專案自動建立各容器服務 (若均不自動建立將跳過 Docker Host 設定):{C_RESET}")
    opt_gitea = interactive_prompt("  是否由本精靈自動建立 Gitea Server 容器? (若已有現成實例請選 N) [y/N]", default="N")
    config["gitea_auto_provision"] = opt_gitea.lower().startswith("y")
    opt_runner = interactive_prompt("  是否由本精靈自動建立 Gitea Act Runner CI/CD 容器? [y/N]", default="N")
    config["with_gitea_runner"] = opt_runner.lower().startswith("y")
    opt_agy = interactive_prompt("  是否由本精靈自動建立 AGY-Remote AI SRE 運維容器? [y/N]", default="N")
    config["with_agy_remote"] = opt_agy.lower().startswith("y")

    needs_docker = config["gitea_auto_provision"] or config["with_gitea_runner"] or config["with_agy_remote"]

    # 3. Docker 容器宿主機設定 (選完需要才會跳出，不需要時跳過)
    if needs_docker:
        print(f"\n{C_BOLD}容器服務運行主機 (Docker Host Configuration):{C_RESET}")
        config["docker_host"] = interactive_prompt("  Docker 運行主機 (輸入 'localhost' 或遠端伺服器 IP/主機名稱)", default=defaults["docker_host"])
        if config["docker_host"] not in ("localhost", "127.0.0.1"):
            config["docker_user"] = interactive_prompt(f"  Docker 主機 SSH 登入帳號 ({config['docker_host']})", default=defaults["docker_user"])
            config["docker_port"] = int(interactive_prompt(f"  Docker 主機 SSH 連線端口", default=str(defaults["docker_port"])))
        else:
            config["docker_user"] = defaults["admin_user"]
            config["docker_port"] = defaults["docker_port"]
    else:
        print(f"\n  {C_DIM}[•] 未勾選自動建立容器服務，略過 Docker 宿主機設定。{C_RESET}")
        config["docker_host"] = "localhost"
        config["docker_user"] = defaults["admin_user"]
        config["docker_port"] = defaults["docker_port"]

    # 4. Gitea 版本控制平台設定
    print(f"\n{C_BOLD}版本控制平台設定 (Gitea Service Configuration):{C_RESET}")
    if config["gitea_auto_provision"]:
        config["gitea_url"] = interactive_prompt("  預計為 Gitea 配置之 URL", default=defaults["gitea_url"])
        config["org"] = interactive_prompt("  Gitea 組織名稱 (Organization)", default=defaults.get("org", config["cluster_name"]))
        config["gitea_user"] = interactive_prompt("  預計初始化之管理員帳號", default=defaults["gitea_user"])
        config["gitea_password"] = interactive_prompt("  預計初始化之管理員密碼", default=defaults["gitea_password"], is_secret=True)
        config["repo_prefix"] = interactive_prompt("  倉庫命名前綴 (Repo Prefix)", default=defaults["repo_prefix"])
        print(f"  {C_CYAN}[•] Gitea 將由 lab-init 於後續階段在 Docker 主機上自動建立！{C_RESET}")
    else:
        config["gitea_url"] = interactive_prompt("  現有內部 Gitea URL", default=defaults["gitea_url"])
        config["org"] = interactive_prompt("  Gitea 組織名稱 (Organization)", default=defaults.get("org", config["cluster_name"]))
        config["gitea_user"] = interactive_prompt("  Gitea 管理員帳號", default=defaults["gitea_user"])
        config["gitea_password"] = interactive_prompt("  Gitea 管理員密碼", default=defaults["gitea_password"], is_secret=True)
        config["repo_prefix"] = interactive_prompt("  倉庫命名前綴 (Repo Prefix)", default=defaults["repo_prefix"])

    # 5. GitHub 平台納管引導提示
    print(f"\n{C_BOLD}外部平台與聯邦擴充 (External Platform Extensions):{C_RESET}")
    gh_choice = interactive_prompt("是否關聯/納管外部 GitHub 平台? (Associate GitHub Account?) [y/N]", default="N")
    if gh_choice.lower().startswith("y"):
        config["github_enabled"] = True
        config["github_owner"] = interactive_prompt("  GitHub 帳號/組織名稱 (GitHub Owner/User)", default=config["admin_user"])
        config["github_token"] = interactive_prompt("  GitHub PAT Token (需勾選 admin:public_key 最小權限)", default=defaults["github_token"], is_secret=True)
        if config["github_token"]:
            print(f"  • 正在透過 GitHub REST API 驗證 Token 有效性...")
            ok, user_or_err = validate_github_token(config["github_token"])
            if ok:
                print(f"  {C_GREEN}[✓] GitHub 帳號驗證成功: {user_or_err}{C_RESET}")
            else:
                print(f"  {C_YELLOW}[!] 警告：GitHub Token 驗證失敗或無外網連線 ({user_or_err})，仍將存入 Actions Secrets。{C_RESET}")
    else:
        config["github_enabled"] = False
        config["github_owner"] = ""
        config["github_token"] = ""

    return config


def export_site_manifest(cluster_config, output_path=None):
    """
    Archinstall-Style Persistent Declaration Export [INV-03].
    Serializes interactive session parameters into a declarative site YAML manifest.
    """
    repo_prefix = cluster_config.get("repo_prefix", "openlab")
    wd = _get_work_dir()
    if output_path:
        out_file = Path(output_path)
    elif wd:
        out_file = wd / "conf" / f"{repo_prefix}.manifest.yml"
    else:
        out_file = OPS_DIR / "conf" / f"{repo_prefix}.manifest.yml"

    cur_lang = cluster_config.get("lang", "en_US" if "openlab" in OPS_DIR.name.lower() else "zh_TW")
    cur_loc = cluster_config.get("locale", f"{cur_lang}.UTF-8")
    c_name = cluster_config.get("cluster_name", "OpenLabOps")
    domain = cluster_config.get("domain", "lab")
    admin_u = cluster_config.get("admin_user", "labadmin")
    ansible_u = cluster_config.get("ansible_user", "lab")

    g_url = cluster_config.get("gitea_url", "http://gitea.lab")
    g_org = cluster_config.get("org", c_name)

    g_host = "gitea.lab"
    g_port = 80
    if "://" in g_url:
        u_body = g_url.split("://", 1)[1].rstrip("/")
        if ":" in u_body:
            g_host, p_str = u_body.split(":", 1)
            try:
                g_port = int(p_str)
            except ValueError:
                g_port = 80
        else:
            g_host = u_body
            g_port = 443 if g_url.startswith("https") else 80

    tz = "UTC"

    is_openlab = (
        "openlab" in repo_prefix.lower()
        or "openlab" in c_name.lower()
        or ansible_u == "ansible"
        or "openlab" in OPS_DIR.name.lower()
    )
    if is_openlab:
        ans_key = f"{ansible_u}.key"
        usr_key = "id_user.key"
        git_key = "git.key"
        gitea_ip = g_host if g_host.replace(".", "").isdigit() else "192.168.1.90"
    else:
        ans_key = "ansible.key"
        usr_key = "id_user.key"
        git_key = "git.key"
        gitea_ip = g_host if g_host.replace(".", "").isdigit() else "192.168.1.90"

    yaml_lines = [
        "# ==============================================================================",
        f"# {c_name} Site Configuration Manifest (conf/{repo_prefix}.manifest.yml)",
        "# USER-EDITABLE CLUSTER TOPOLOGY & SITE DECLARATION (Archinstall-Style Export)",
        "# Framework schema & repository definitions are governed by conf/core.manifest.yml.",
        "# ==============================================================================",
        "",
        "# 1. 叢集身份與環境宣告",
        "cluster:",
        f'  name: "{c_name}"',
        f'  domain: "{domain}"',
        f'  admin_user: "{admin_u}"',
        f'  ansible_user: "{ansible_u}"',
        f'  timezone: "{tz}"',
        f'  locale: "{cur_loc}"',
        f'  lang: "{cur_lang}"',
        "",
        "# 2. 本地 Gitea 與平臺實例定義",
        "git_platform:",
        f'  host: "{g_host}"',
        f'  ip: "{gitea_ip}"',
        "  ssh_port: 22",
        f"  http_port: {g_port}",
        f'  org: "{g_org}"',
        f'  repo_prefix: "{repo_prefix}"',
        "",
        "# 3. 三大核心語意金鑰實體宣告 (Canonical Keys Mapping)",
        "keys:",
        f'  ansible: "{ans_key}"                       # Ansible 自動化連線私鑰',
        f'  user: "{usr_key}"                     # 管理者通用私鑰',
        f'  git: "{git_key}"                  # 版本控制平台 Gitea/Git 存取私鑰',
        "",
        "# 4. 服務與擴充元件設定",
        "services:",
        f'  docker_host: "{cluster_config.get("docker_host", "localhost")}"',
        f'  gitea_auto_provision: {str(cluster_config.get("gitea_auto_provision", False)).lower()}',
        f'  with_gitea_runner: {str(cluster_config.get("with_gitea_runner", False)).lower()}',
        f'  with_agy_remote: {str(cluster_config.get("with_agy_remote", False)).lower()}',
        "",
        "extensions:",
        "  github:",
        f'    enabled: {str(cluster_config.get("github_enabled", False)).lower()}',
        f'    owner: "{cluster_config.get("github_owner", "")}"',
        ""
    ]

    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
        print(f"  {C_GREEN}[✓] Site Manifest exported to: {out_file} (Archinstall-Style Persistent Declaration){C_RESET}")
        return True
    except Exception as e:
        print(f"  {C_YELLOW}[!] Could not export site manifest: {e}{C_RESET}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 2. Environment Preflight Verification & Resource Assembly
# ──────────────────────────────────────────────────────────────────────────────
def run_environment_preflight(cluster_config):
    """
    確認環境整理檢查：集合並校驗散落的基礎環境與外部組件
    - 檢查 OpenSSH Client (ssh, ssh-keygen)
    - 檢查 Docker Host 連通性與權限 (本地或遠端 SSH)
    - 檢查 Gitea 服務連通性 (現成實例驗證或自舉準備)
    - 檢查 GitHub 平台連線與憑證有效性
    """
    print(f"  • [1/4] Checking Local Toolchain (OpenSSH & Git)...")
    has_ssh = shutil.which("ssh") is not None
    has_keygen = shutil.which("ssh-keygen") is not None
    if has_ssh and has_keygen:
        print(f"    {C_GREEN}[✓] OpenSSH toolchain available.{C_RESET}")
    else:
        print(f"    {C_RED}[✗] OpenSSH client or ssh-keygen missing.{C_RESET}")

    d_host = cluster_config.get("docker_host", "localhost")
    needs_docker = (
        cluster_config.get("gitea_auto_provision")
        or cluster_config.get("with_gitea_runner")
        or cluster_config.get("with_agy_remote")
    )
    print(f"  • [2/4] Checking Docker Host Reachability ({d_host})...")
    if not needs_docker:
        print(f"    {C_DIM}[•] Skipped Docker host check (No container services requested).{C_RESET}")
    elif d_host in ("localhost", "127.0.0.1"):
        has_docker_cli = shutil.which("docker") is not None
        has_docker = False
        if has_docker_cli:
            try:
                has_docker = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
            except Exception:
                has_docker = False
        if has_docker:
            print(f"    {C_GREEN}[✓] Local Docker daemon reachable.{C_RESET}")
        else:
            print(f"    {C_YELLOW}[!] Local Docker daemon not reachable or docker CLI not found.{C_RESET}")
    else:
        d_user = cluster_config.get("docker_user", "root")
        d_port = str(cluster_config.get("docker_port", 22))
        res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=3",
                             "-p", d_port, f"{d_user}@{d_host}", "docker info || sudo docker info"],
                             capture_output=True, text=True)
        if res.returncode == 0:
            print(f"    {C_GREEN}[✓] Remote Docker host ({d_host}) accessible via SSH.{C_RESET}")
        else:
            print(f"    {C_YELLOW}[!] Remote Docker host ({d_host}) SSH check returned code {res.returncode}.{C_RESET}")

    print(f"  • [3/4] Checking Gitea Platform Setup...")
    if cluster_config.get("gitea_auto_provision"):
        print(f"    {C_CYAN}[•] Gitea marked for automatic container provisioning.{C_RESET}")
    else:
        g_url = cluster_config.get("gitea_url", "http://gitea.lab:3000")
        try:
            req = urllib.request.Request(f"{g_url.rstrip('/')}/api/v1/version", headers={"User-Agent": "lab-init"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                print(f"    {C_GREEN}[✓] Existing Gitea reachable at {g_url}.{C_RESET}")
        except Exception:
            print(f"    {C_YELLOW}[!] Existing Gitea not reachable yet ({g_url}). Proceeding with onboarding.{C_RESET}")

    print(f"  • [4/4] Checking External Platforms...")
    if cluster_config.get("github_enabled"):
        print(f"    {C_GREEN}[✓] GitHub federation enabled (Owner: {cluster_config.get('github_owner')}).{C_RESET}")
    else:
        print(f"    {C_DIM}[•] GitHub federation disabled (Pure Air-Gapped Mode).{C_RESET}")

    print(f"\n  {C_BOLD}{C_GREEN}[✓] Environment Preflight & Resource Assembly Complete.{C_RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Ephemeral Bootstrap Key Generation
# ──────────────────────────────────────────────────────────────────────────────
def generate_ephemeral_key():
    """於臨時隔離目錄生成無密碼 Ed25519 金鑰對，遵守 INV-02 規範"""
    import atexit
    temp_dir = Path("/tmp/lab_bootstrap_keys")
    temp_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    atexit.register(lambda: shutil.rmtree("/tmp/lab_bootstrap_keys", ignore_errors=True))
    temp_key = temp_dir / "id_ed25519"
    temp_pub = temp_dir / "id_ed25519.pub"

    if not temp_key.exists():
        subprocess.run([
            "ssh-keygen", "-t", "ed25519", "-N", "",
            "-f", str(temp_key),
            "-C", "ephemeral-bootstrap@openlab"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    pub_text = temp_pub.read_text(encoding="utf-8").strip()
    print(f"  [✓] Ephemeral Bootstrap Key Pair created at: {C_YELLOW}{temp_dir}{C_RESET}")
    print(f"  [✓] Fingerprint: {pub_text[:30]}...{pub_text[-15:]}")
    return temp_key, pub_text


# ──────────────────────────────────────────────────────────────────────────────
# 3. Dynamic Node Ingestion (lab-node) with Ephemeral Key (NO from IP limitation)
# ──────────────────────────────────────────────────────────────────────────────
def run_node_ingestion(targets, ephemeral_pubkey, legacy_key_path=None, non_interactive=False, dialog=None):
    """
    執行節點探測與開門：
    初期探測公鑰不施加 from IP 限制，待所有節點網路資料搜集完畢並定義 Subnet 後，
    再由金鑰輪轉動作生成正式金鑰並注入定義好的 from IP！
    若節點因 Sudo 密碼或連線失敗，立即引導至統一節點救援對話框 (<Retry Node> / <Skip Node>)。
    """
    from engine.onboard import onboard_node, prompt_node_rescue_dialog
    import getpass

    def _prompt_cb(msg: str, secret: bool = True) -> Optional[str]:
        if dialog:
            return dialog.password_dialog("In-Flight Authentication", msg)
        elif not non_interactive and sys.stdin.isatty():
            try:
                if secret:
                    return getpass.getpass(f"\n{msg} ")
                return input(f"\n{msg} ")
            except (KeyboardInterrupt, EOFError):
                return None
        return None

    results = []
    for t in list(targets):
        t_ip = t.get("ip")
        t_name = t.get("name", t_ip)
        t_scen = t.get("scenario", "password_only")
        t_cat = t.get("node_category") or t.get("inv_group_role") or None
        t_target = t.get("target_user")
        if not t_target:
            t_target = "root" if t_cat in ("appliance", "hypervisor", "storage") else "lab"

        while True:
            t_user = t.get("initial_user") or t.get("user") or "labadmin"
            t_port = int(t.get("ssh_port") or t.get("port") or 22)
            t_pass = t.get("initial_password")
            if t_scen == "password_only" and not t_pass:
                t_pass = "labtest123"
            t_key = t.get("key_file") or legacy_key_path

            if dialog:
                node_res = [False, None]
                def _do_onboard(log_fn):
                    ok, facts_or_err = onboard_node(
                        host=t_ip,
                        user=t_user,
                        port=t_port,
                        password=t_pass,
                        key_file=t_key,
                        target_user=t_target,
                        ephemeral_pubkey=ephemeral_pubkey,
                        allowed_subnets=None,
                        interactive=False,
                        callback=log_fn,
                        node_category=t_cat,
                        prompt_callback=_prompt_cb
                    )
                    node_res[0] = ok
                    node_res[1] = facts_or_err
                    return ok

                dialog.progress_box(
                    f"Node Ingestion: {t_name}",
                    f"Connecting to {t_user}@{t_ip}:{t_port}...",
                    _do_onboard,
                    width=76,
                    height=20
                )
                ok, facts_or_err = node_res[0], node_res[1]
            else:
                ok, facts_or_err = onboard_node(
                    host=t_ip,
                    user=t_user,
                    port=t_port,
                    password=t_pass,
                    key_file=t_key,
                    target_user=t_target,
                    ephemeral_pubkey=ephemeral_pubkey,
                    allowed_subnets=None,
                    interactive=False,
                    node_category=t_cat,
                    prompt_callback=_prompt_cb
                )

            if ok:
                if isinstance(facts_or_err, dict):
                    t.update(facts_or_err)
                results.append((t_name, t_ip, True, facts_or_err))
                break
            else:
                err_msg = str(facts_or_err or "連線逾時或認證失敗")
                if non_interactive:
                    results.append((t_name, t_ip, False, facts_or_err))
                    break

                # 彈出統一救援對話框
                action = prompt_node_rescue_dialog(t, err_msg, dialog=dialog, non_interactive=non_interactive)
                if action == "retry":
                    t_scen = t.get("scenario", "key_auth")
                    continue
                else:
                    print(f"  {C_YELLOW}[!] 略過節點: {t_name} ({t_ip}) (維運者選擇放棄){C_RESET}")
                    results.append((t_name, t_ip, False, facts_or_err))
                    break

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 4. Subnet Analysis & Inventory Classification
# ──────────────────────────────────────────────────────────────────────────────
def run_subnet_discovery_and_classification():
    """執行多維分類引擎，動態解析節點網路並產出 inventory/hosts.yml"""
    res = subprocess.run([sys.executable, str(ENGINE_DIR / "classifier.py"), "--apply"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  {C_RED}[✗] Classifier error: {res.stderr.strip()}{C_RESET}")

    # 提取所有探測到的真實子網路
    discovered_subnets = []
    nodes_files = list(_get_nodes_dir().glob("*.json"))
    for nf in nodes_files:
        if nf.name == "current.json":
            continue
        try:
            data = json.loads(nf.read_text(encoding="utf-8"))
            s_cidr = data.get("subnet_cidr")
            if s_cidr and s_cidr not in discovered_subnets:
                discovered_subnets.append(s_cidr)
        except Exception:
            pass

    print(f"  [✓] Discovered Network Subnets: {C_GREEN}{', '.join(discovered_subnets)}{C_RESET}")
    print(f"  [✓] Compiled Ansible inventory: {C_GREEN}{INVENTORY_DIR / 'hosts.yml'}{C_RESET}")
    return discovered_subnets, {}


# ──────────────────────────────────────────────────────────────────────────────
# 5. Official Key Generation & Rotation Handover (Action / Playbook driven)
# ──────────────────────────────────────────────────────────────────────────────
def run_key_rotation_handover(targets, ephemeral_key_path, ephemeral_pubkey, allowed_from_subnets, ansible_user="lab", callback=None):
    """
    金鑰輪換交接階段 (正式 Action 產生金鑰與注入定義好的 from IP)：
    1. 產生正式生產金鑰 (~/.ssh/ansible.key)
    2. 使用臨時引導金鑰登入，追加正式公鑰並塞入定義好的 from IP (from="{allowed_from_subnets}")
    3. 使用新私鑰驗證 SSH 連線
    4. 自受控端 authorized_keys 中徹底抹除臨時引導公鑰 (remove_old_key)
    5. 本地銷毀臨時私鑰
    """
    def _log(msg):
        if callback:
            try:
                callback(msg)
            except Exception:
                pass
        else:
            print(msg)

    _log(f"\n{C_CYAN}  • Generating Permanent Production SSH Key Pair for '{ansible_user}'...{C_RESET}")
    ssh_home = Path(os.environ.get("LAB_SSH_HOME", str(Path.home() / ".ssh")))
    ssh_home.mkdir(mode=0o700, exist_ok=True)
    perm_key = ssh_home / f"{ansible_user}.key"
    perm_pub = ssh_home / f"{ansible_user}.pub"

    keygen_pub = Path(str(perm_key) + ".pub")
    if not perm_key.exists():
        subprocess.run([
            "ssh-keygen", "-t", "ed25519", "-N", "",
            "-f", str(perm_key),
            "-C", f"{ansible_user}@openlab-master"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        perm_key.chmod(0o600)
    else:
        _log(f"  [•] Existing Permanent Key preserved: {C_GREEN}{perm_key}{C_RESET}")

    if keygen_pub.exists():
        perm_pub_text = keygen_pub.read_text(encoding="utf-8").strip()
        perm_pub.write_text(perm_pub_text + "\n", encoding="utf-8")
    elif perm_pub.exists():
        perm_pub_text = perm_pub.read_text(encoding="utf-8").strip()
    else:
        res = subprocess.run(["ssh-keygen", "-y", "-f", str(perm_key)], capture_output=True, text=True, check=True)
        perm_pub_text = res.stdout.strip()
        perm_pub.write_text(perm_pub_text + "\n", encoding="utf-8")

    _log(f"  [✓] Permanent Key Generated: {C_GREEN}{perm_key}{C_RESET}")
    _log(f"  • Injecting Defined from IP Restriction: {C_YELLOW}from=\"{allowed_from_subnets}\"{C_RESET}")

    # 1. 優先透過官方 Ansible 劇本 (rotate-ansible-keys.yml) 執行正式三階段輪換
    ansible_bin = shutil.which("ansible-playbook")
    playbook_file = OPS_DIR / "ansible" / "playbooks" / "rotate-ansible-keys.yml"
    inventory_file = _get_inventory_dir() / "hosts.yml"
    if not inventory_file.exists():
        inventory_file = OPS_DIR / "ansible" / "inventory" / "hosts.yml"

    playbook_servers_rotated = False
    if ansible_bin and playbook_file.exists() and inventory_file.exists():
        _log(f"  • Invoking Official Ansible Playbook: {playbook_file.name} (Three-Stage Protocol)...")
        rot_cmd = [
            ansible_bin,
            "-i", str(inventory_file),
            str(playbook_file),
            "-e", f"bootstrap_key={ephemeral_key_path}",
            "-e", f"target_hosts=servers",
            "-e", f"ansible_user={ansible_user}",
            "-e", f"custom_pub_key_path={perm_pub}",
            "-e", f"new_pub_key_path={perm_pub}",
            "-e", f"new_priv_key_path={perm_key}",
            "-e", f"old_pub_key={ephemeral_pubkey}",
            "-e", f"ansible_key_options=from=\"{allowed_from_subnets}\""
        ]
        res = subprocess.run(rot_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            _log(f"  {C_GREEN}[✓] Fleet Servers key rotation succeeded via rotate-ansible-keys.yml!{C_RESET}")
            playbook_servers_rotated = True
        else:
            _log(f"  {C_YELLOW}[!] Note: Ansible playbook rotation output:\n{res.stdout.strip()[-300:] if res.stdout else ''}{C_RESET}")

    all_rotated = True
    for t in targets:
        t_ip = t.get("ip")
        t_name = t.get("name", t_ip)
        is_appliance = t.get("node_category") in ("appliance", "hypervisor", "storage") or t.get("inv_group_role") == "appliances" or t.get("appliance_type") in ("storage", "kvm")
        t_target_user = t.get("target_user")
        if not t_target_user:
            t_target_user = "root" if is_appliance else ansible_user
        t_port = int(t.get("ssh_port") or t.get("port") or 22)

        # 若已由 Ansible Playbook 成功輪換非家電伺服器，直接進入連線驗證
        if playbook_servers_rotated and not is_appliance and t_target_user == ansible_user:
            _log(f"  • Verifying Handover on [{t_name}] ({t_ip}) with Permanent Key...")
        else:
            _log(f"  • Rotating SSH Key on [{t_name}] ({t_ip})...")

            # 準備注入指令：加入新公鑰 (含 from IP)，並移除舊臨時公鑰
            new_entry = f'from="{allowed_from_subnets}" {perm_pub_text}'
            q_user = shlex.quote(str(t_target_user))
            q_new_entry = shlex.quote(new_entry)
            q_eph_pub = shlex.quote(str(ephemeral_pubkey))
            rotate_script = f"""
set -e
/sbin/mount -u -w /cf 2>/dev/null || true
TARGET_USER={q_user}
USER_HOME=""
if command -v getent >/dev/null 2>&1; then
    USER_HOME=$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6 || true)
fi
if [ -z "$USER_HOME" ] && [ -f /etc/passwd ]; then
    USER_HOME=$(grep -E "^${{TARGET_USER}}:" /etc/passwd 2>/dev/null | cut -d: -f6 || true)
fi
if [ -z "$USER_HOME" ] || [ ! -d "$USER_HOME" ]; then
    if [ "$TARGET_USER" = "root" ]; then
        USER_HOME="/root"
    else
        USER_HOME="/home/$TARGET_USER"
    fi
fi
AUTH_FILE="$USER_HOME/.ssh/authorized_keys"
[ -f /cf/conf/authorized_keys ] && AUTH_FILE="/cf/conf/authorized_keys"
[ -f /etc/ssh/keys-root/authorized_keys ] && AUTH_FILE="/etc/ssh/keys-root/authorized_keys"
mkdir -p "$USER_HOME/.ssh" 2>/dev/null || true
chmod 0700 "$USER_HOME/.ssh" 2>/dev/null || true

# Stage 1: Add permanent public key with defined from IP
printf '%s\\n' {q_new_entry} >> "$AUTH_FILE"

# Stage 2: Remove old ephemeral bootstrap key
grep -vF -- {q_eph_pub} "$AUTH_FILE" > "$AUTH_FILE.tmp" || true
if [ -s "$AUTH_FILE.tmp" ] || [ -f "$AUTH_FILE.tmp" ]; then
    mv -f "$AUTH_FILE.tmp" "$AUTH_FILE"
fi
chmod 0600 "$AUTH_FILE"
[ -f /cf/conf/authorized_keys ] && cp -f /cf/conf/authorized_keys /root/.ssh/authorized_keys 2>/dev/null || true
/sbin/mount -u -r /cf 2>/dev/null || true
[ -x /sbin/auto-backup.sh ] && /sbin/auto-backup.sh >/dev/null 2>&1 || true
"""
            # 決定登入執行的連線指令 (支援現有正式金鑰、臨時引導金鑰或節點指定私鑰)
            candidate_keys = []
            if perm_key and perm_key.exists():
                candidate_keys.append(perm_key)
            if ephemeral_key_path and ephemeral_key_path.exists() and ephemeral_key_path not in candidate_keys:
                candidate_keys.append(ephemeral_key_path)
            if t.get("key_file"):
                kf = Path(os.path.expanduser(t["key_file"]))
                if kf.exists() and kf not in candidate_keys:
                    candidate_keys.append(kf)

            working_key = None
            for cand_k in candidate_keys:
                test_cmd = [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "IdentitiesOnly=yes",
                    "-o", "ConnectTimeout=4",
                    "-p", str(t_port),
                    "-i", str(cand_k),
                    f"{t_target_user}@{t_ip}",
                    "true"
                ]
                r = subprocess.run(test_cmd, capture_output=True)
                if r.returncode == 0:
                    working_key = cand_k
                    break

            if working_key:
                cmd = [
                    "ssh",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "IdentitiesOnly=yes",
                    "-p", str(t_port),
                    "-i", str(working_key),
                    f"{t_target_user}@{t_ip}",
                    "sh"
                ]
                res = subprocess.run(cmd, input=rotate_script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                # 若無免密金鑰可用，嘗試使用 PTY 模擬執行 (避免終端密碼提示破壞 Curses)
                from engine.onboard import execute_pty_ssh
                u = t.get("initial_user") or t.get("user") or t_target_user
                p = t.get("initial_password")
                k = t.get("key_file")
                inner_cmd = (
                    f"TARGET_USER={q_user}; "
                    f"USER_HOME=$(getent passwd \"$TARGET_USER\" 2>/dev/null | cut -d: -f6 || echo \"/home/$TARGET_USER\"); "
                    f"[ -z \"$USER_HOME\" ] && USER_HOME=\"/home/$TARGET_USER\"; "
                    f"mkdir -p \"$USER_HOME/.ssh\" && chmod 0700 \"$USER_HOME/.ssh\" && "
                    f"printf '%s\\n' {q_new_entry} >> \"$USER_HOME/.ssh/authorized_keys\" && "
                    f"chmod 0600 \"$USER_HOME/.ssh/authorized_keys\""
                )
                code, out = execute_pty_ssh(
                    host=t_ip,
                    user=u,
                    port=t_port,
                    password=p,
                    key_file=k,
                    command=f"sudo sh -c {shlex.quote(inner_cmd)}",
                    timeout=15
                )
                res = subprocess.CompletedProcess(args=[], returncode=code, stderr=out if code != 0 else "")

            if res.returncode != 0:
                _log(f"  {C_RED}[✗] Failed to rotate key on {t_name} ({t_ip}): {res.stderr.strip()}{C_RESET}")
                all_rotated = False
                continue

        # Stage 3: 使用正式新私鑰驗證連線 (嚴格 BatchMode 零卡死)
        verify_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=5",
            "-p", str(t_port),
            "-i", str(perm_key),
            f"{t_target_user}@{t_ip}",
            "echo 'OK'"
        ]
        v_res = subprocess.run(verify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if v_res.returncode == 0:
            _log(f"  {C_GREEN}[✓] Handover Verified on {t_name} ({t_ip}) with Permanent Key & Defined from IP!{C_RESET}")
        else:
            _log(f"  {C_RED}[✗] Verification failed on {t_name} ({t_ip}) with Permanent Key!{C_RESET}")
            all_rotated = False

    # 銷毀本地臨時金鑰與隔離目錄 (Zero Residual [INV-11])
    shutil.rmtree("/tmp/lab_bootstrap_keys", ignore_errors=True)
    _log(f"  [✓] Ephemeral Bootstrap Keys purged from /tmp/ (Zero Residual).")

    return all_rotated


# ──────────────────────────────────────────────────────────────────────────────
# 6. Optional Components: Gitea Runner & AGY-Remote (Dockerfile-Driven)
# ──────────────────────────────────────────────────────────────────────────────
def deploy_compose_service(service_name, service_dir, cluster_config, env_vars=None):
    """
    支援 Local 或 Remote Docker Host 部署容器服務：
    - 若 docker_host == 'localhost' 或 '127.0.0.1'：本機執行 docker compose up -d
    - 若 docker_host 為遠端主機：透過 SSH 遠端建立目錄、寫入 compose 檔案並以 docker compose 啟動
    """
    d_host = cluster_config.get("docker_host", "localhost")
    d_user = cluster_config.get("docker_user", cluster_config.get("admin_user", "root"))
    d_port = str(cluster_config.get("docker_port", 22))

    compose_file = service_dir / "docker-compose.yml"
    if not compose_file.exists():
        print(f"  {C_RED}[✗] docker-compose.yml not found at {compose_file}{C_RESET}")
        return False

    compose_content = compose_file.read_text(encoding="utf-8")

    if d_host in ("localhost", "127.0.0.1"):
        print(f"  • Deploying {service_name} on local Docker host...")
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        subprocess.run(["docker", "compose", "-f", str(compose_file), "up", "-d"], env=env, check=False)
        print(f"  {C_GREEN}[✓] {service_name} started on local Docker host.{C_RESET}")
        return True

    # Remote Docker Host 部署
    print(f"  • Deploying {service_name} to remote Docker host: {d_user}@{d_host}:{d_port}...")
    if not re.match(r"^[a-zA-Z0-9._-]+$", str(service_name)):
        print(f"  {C_RED}[✗] Invalid service name: {service_name}{C_RESET}")
        return False
    remote_dir = f"/opt/{service_name}"
    q_remote_dir = shlex.quote(remote_dir)
    ssh_opts = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-p", d_port, f"{d_user}@{d_host}"]

    # 1. 確保遠端目標目錄存在
    subprocess.run(ssh_opts + [f"mkdir -p {q_remote_dir}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. 串流上傳 docker-compose.yml
    p = subprocess.Popen(ssh_opts + [f"cat > {q_remote_dir}/docker-compose.yml"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.communicate(input=compose_content.encode("utf-8"))

    # 3. 串流上傳 .env 環境變數
    if env_vars:
        env_lines = "\n".join([f"{k}={v}" for k, v in env_vars.items()]) + "\n"
        p = subprocess.Popen(ssh_opts + [f"cat > {q_remote_dir}/.env"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.communicate(input=env_lines.encode("utf-8"))

    # 4. 遠端執行 docker compose up -d (支援直接執行或 sudo 提權)
    remote_cmd = f"cd {q_remote_dir} && (docker compose up -d || sudo docker compose up -d)"
    res = subprocess.run(ssh_opts + [remote_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"  {C_GREEN}[✓] {service_name} successfully deployed and running on remote Docker host ({d_host})!{C_RESET}")
        return True
    else:
        print(f"  {C_YELLOW}[!] Note: Remote docker compose output: {res.stderr.strip() or res.stdout.strip()}{C_RESET}")
        return False


def setup_optional_gitea_runner(cluster_config, non_interactive=False):
    """選配：建置並設定 Gitea Act Runner 容器 (支援本地或遠端 Docker 主機)"""
    print(f"\n{C_CYAN}  • [Optional] Setting up Gitea Act Runner...{C_RESET}")
    candidate_dirs = [
        OPS_DIR / "extensions" / "containers" / "gitea-runner",
        OPS_DIR / "docker" / "gitea-runner"
    ]
    runner_dir = None
    for d in candidate_dirs:
        if d.exists():
            runner_dir = d
            break

    if not runner_dir or not (runner_dir / "docker-compose.yml").exists():
        print(f"  {C_RED}[✗] Runner compose specification not found in candidate paths.{C_RESET}")
        return False

    token = None
    if not non_interactive:
        token = interactive_prompt("Enter Gitea Runner Registration Token (leave blank to auto-fetch or skip)", default="")

    if not token:
        # 嘗試透過 Admin API 自動取得 Runner 註冊 Token
        try:
            g_url = cluster_config.get("gitea_url", "http://gitea.lab:3000").rstrip("/")
            u = cluster_config.get("gitea_user", "labadmin")
            p = cluster_config.get("gitea_password", "labtest123")
            auth_str = base64.b64encode(f"{u}:{p}".encode("utf-8")).decode("ascii")
            for ep in [f"{g_url}/api/v1/admin/runners/registration-token", f"{g_url}/api/v1/orgs/{cluster_config.get('org', 'OpenLabOps')}/runners/registration-token"]:
                t_req = urllib.request.Request(ep, headers={"Authorization": f"Basic {auth_str}", "User-Agent": "OpenLabOps-Init"})
                try:
                    with urllib.request.urlopen(t_req, timeout=4) as t_resp:
                        if t_resp.status in (200, 201):
                            t_data = json.loads(t_resp.read().decode("utf-8"))
                            token = t_data.get("token", "")
                            if token:
                                print(f"  {C_GREEN}[✓] Automatically retrieved Runner Registration Token from Gitea API.{C_RESET}")
                                break
                except Exception:
                    pass
        except Exception:
            pass

    if token:
        env_vars = {
            "GITEA_INSTANCE_URL": cluster_config.get("gitea_url", "http://gitea.lab:3000"),
            "GITEA_RUNNER_REGISTRATION_TOKEN": token,
            "GITEA_RUNNER_LABELS": "ansible:host,native:host,ubuntu-latest:host"
        }
        return deploy_compose_service("gitea-runner", runner_dir, cluster_config, env_vars=env_vars)
    else:
        print(f"  [•] Runner spec ready. Start manually via: docker compose -f {runner_dir}/docker-compose.yml up -d")
        return True


def setup_optional_agy_remote(cluster_config, non_interactive=False):
    """選配：建置並設定 AGY-Remote 開發容器 (支援本地或遠端 Docker 主機)"""
    print(f"\n{C_CYAN}  • [Optional] Setting up AGY-Remote Container...{C_RESET}")
    candidate_dirs = [
        OPS_DIR / "extensions" / "containers" / "remote-dev",
        OPS_DIR / "docker" / "remote-dev"
    ]
    agy_dir = None
    for d in candidate_dirs:
        if d.exists():
            agy_dir = d
            break

    if not agy_dir or not (agy_dir / "docker-compose.yml").exists():
        print(f"  {C_RED}[✗] AGY-Remote compose specification not found.{C_RESET}")
        return False

    return deploy_compose_service("remote-dev", agy_dir, cluster_config)


# ──────────────────────────────────────────────────────────────────────────────
# Master Main Controller
# ──────────────────────────────────────────────────────────────────────────────
def _get_engine_version() -> str:
    ver_file = OPS_DIR / "VERSION"
    if ver_file.exists():
        return ver_file.read_text(encoding="utf-8").strip() or "1.0.0"
    return "1.0.0"

def main():
    parser = argparse.ArgumentParser(prog="lab-init", description="OpenLabOps Day-0 Initialization Commander (bin/lab-init)")
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Day-0 Initialization Commander (lab-init) v{_get_engine_version()}")
    parser.add_argument("--lang", choices=["zh_TW", "en_US", "ja_JP"], help="Language/Locale for setup wizard and deployed cluster (zh_TW|en_US|ja_JP)")
    parser.add_argument("--manifest", help="Day-0 declarative onboarding manifest (e.g. tests/conf/day0_mock_fleet.yml)")
    parser.add_argument("--legacy-key", help="Legacy SSH private key path for mixed-scenario targets")
    parser.add_argument("--non-interactive", action="store_true", help="Run without human interactive prompts")
    parser.add_argument("--with-gitea-runner", action="store_true", help="Optionally configure and build Gitea Act Runner container")
    parser.add_argument("--with-remote-dev", dest="with_agy_remote", action="store_true", help="Optionally build and provision AGY-Remote container")
    parser.add_argument("--skip-nodes", help="Comma-separated list of host names to skip (e.g. gateway,node2)")
    parser.add_argument("--include-appliances", action="store_true", help="Include appliances (Storage/Virtualization) in Day-0 server onboarding")
    parser.add_argument("--include-endpoints", action="store_true", help="Include endpoints (workstations) in Day-0 server onboarding")
    args = parser.parse_args()

    import atexit
    init_work_dir = Path(tempfile.mkdtemp(prefix="lab_init_work_"))
    os.environ["LAB_INIT_WORK_DIR"] = str(init_work_dir)
    os.environ["KIWI_INIT_WORK_DIR"] = str(init_work_dir)
    atexit.register(shutil.rmtree, init_work_dir, ignore_errors=True)

    ui_banner()
    TOTAL_STEPS = 6

    # 步驟 1: 參數收集 (TUI 或 Manifest，含 Gitea/GitHub/Docker/外掛選項)
    step_header(1, TOTAL_STEPS, "Collecting Infrastructure Parameters & Service Intent")
    from engine.onboard import parse_day0_manifest, get_default_homelab_subnets

    skip_nodes_list = [s.strip() for s in args.skip_nodes.split(",")] if args.skip_nodes else []

    manifest_meta = None
    targets = []
    # 在互動模式下載入所有節點 (由 Step 4 的 Checklist 進行 [X] 預設選取與過濾)
    # 在非互動模式下則依 CLI 參數直接過濾
    skip_app_default = not args.include_appliances if args.non_interactive else False
    skip_end_default = not args.include_endpoints if args.non_interactive else False

    if args.manifest:
        m_path = Path(args.manifest)
        if not m_path.exists():
            print(f"{C_RED}Error: Manifest file {m_path} not found.{C_RESET}")
            sys.exit(1)
        manifest_meta, targets = parse_day0_manifest(
            m_path,
            skip_appliances=skip_app_default,
            skip_endpoints=skip_end_default,
            skip_nodes=skip_nodes_list
        )
    else:
        # Archinstall-Style 核心哲學：預設模式完全由使用者互動鍵入與動態探索建立，不預載任何靜態清單
        manifest_meta = None
        targets = []

    cluster_config = setup_base_parameters(manifest_meta, non_interactive=args.non_interactive, cli_lang=args.lang)
    if args.with_gitea_runner:
        cluster_config["with_gitea_runner"] = True
    if args.with_agy_remote:
        cluster_config["with_agy_remote"] = True

    # 步驟 2: 確認環境預檢 (集合並校驗散落的基礎環境與外部組件)
    step_header(2, TOTAL_STEPS, "Preflight Environment Verification & Resource Assembly")
    run_environment_preflight(cluster_config)

    # 步驟 3: 依選項補齊必要工具、容器與臨時金鑰 (Provisioning)
    step_header(3, TOTAL_STEPS, "Provisioning Optional Containers & Ephemeral Bootstrap Keys")

    # 3.1 透過 Gitea REST API 建立 5 大下游聯邦倉庫
    print(f"\n  • Provisioning Gitea Downstream Federation Repositories...")
    org_target = cluster_config.get("org", cluster_config.get("cluster_name", "OpenLabOps"))
    repo_results, bot_token = provision_gitea_federation_repos(
        gitea_url=cluster_config.get("gitea_url", "http://gitea.lab"),
        gitea_user=cluster_config.get("gitea_user", "labadmin"),
        gitea_password=cluster_config.get("gitea_password", "labtest123"),
        org_name=org_target,
        repo_prefix=cluster_config.get("repo_prefix", "openlab")
    )
    if bot_token:
        cluster_config["ci_bot_token"] = bot_token
    for r in repo_results:
        if "HTTP 4" in str(r) or "HTTP 5" in str(r) or "Error" in str(r):
            print(f"    {C_RED}[✗] Federation Repository: {r}{C_RESET}")
        else:
            print(f"    {C_GREEN}[✓] Federation Repository: {r}{C_RESET}")

    # 3.2 直推聯邦基線代碼至 Gitea (免除本機 git clone 5 大下游倉庫)
    push_federation_baselines_to_gitea(
        cluster_config=cluster_config,
        org_name=org_target,
        repo_prefix=cluster_config.get("repo_prefix", "openlab")
    )

    if cluster_config.get("with_gitea_runner"):
        setup_optional_gitea_runner(cluster_config, non_interactive=args.non_interactive)
    else:
        print(f"  [•] Gitea Runner provisioning skipped (Use --with-gitea-runner to enable).")

    if cluster_config.get("with_agy_remote"):
        setup_optional_agy_remote(cluster_config, non_interactive=args.non_interactive)
    else:
        print(f"  [•] AGY-Remote container provisioning skipped. Use --with-remote-dev to enable.")

    eph_key_path, eph_pub_text = generate_ephemeral_key()

    # 步驟 4: 動態節點納管與事實探測 (lab-node 閉環開門)
    step_header(4, TOTAL_STEPS, "Executing Dynamic Node Ingestion & Fact Probing")
    from engine.bsd_dialog import BSDDialog, is_bsd_tui_supported

    use_bsd_tui = is_bsd_tui_supported() and not args.non_interactive

    if use_bsd_tui and targets:
        dialog = BSDDialog(title="OpenLabOps Master Operations Engine", subtitle="Day-0 Target Node Selection")
        checklist_items = []
        for t in targets:
            name = t.get("name", t.get("ip"))
            ip = t.get("ip", name)
            is_app = t.get("is_appliance", False)
            is_end = t.get("is_endpoint", False)

            if is_app:
                desc = "Appliance (Embedded BSD / Storage / Virtualization)"
                default_chk = False
            elif is_end:
                desc = "Admin Workstation Endpoint"
                default_chk = False
            else:
                desc = "Managed Server (Linux)"
                default_chk = True

            checklist_items.append({
                "id": name,
                "name": name,
                "label": f"{name} ({ip})",
                "desc": desc,
                "checked": default_chk
            })

        while True:
            selected_ids, btn = dialog.checklist(
                t("init.step6_title", "Step 6/6: Target Node Selection & Ingestion"),
                t("init.step6_prompt", "請按 [Space] 打 [X] 勾選本次納管之目標主機 (嵌入式與儲存設備預設跳過):"),
                checklist_items,
                buttons=[t("common.confirm", "OK"), "Add Node", t("common.skip_all", "Skip All")],
                width=76,
                height=20
            )
            if btn == "Add Node":
                add_fields = [
                    {"key": "name", "label": "Host Name:", "value": "", "help": "主機名稱 (如 node01)"},
                    {"key": "ip", "label": "IP Address:", "value": "", "help": "主機 IP 位址"},
                    {"key": "role", "label": "Node Category (Role):", "value": "server", "help": "節點類型 (server / dev / desktop / hypervisor / storage)"},
                    {"key": "user", "label": "SSH User:", "value": cluster_config.get("admin_user", "labadmin"), "help": "SSH 帳號"},
                    {"key": "key_file", "label": "Private Key File:", "value": "", "help": "SSH 私鑰路徑 (如 ~/.ssh/id_rsa，若用密碼可留空)"},
                    {"key": "password", "label": "Password / Sudo:", "value": "", "secret": True, "help": "SSH 密碼 (若使用私鑰且免密 sudo 可留空)"},
                    {"key": "port", "label": "SSH Port:", "value": "22", "help": "SSH 連線端口 (預設 22)"},
                ]
                node_vals, n_btn = dialog.form("Add Managed Node", "請輸入新節點連線資訊:", add_fields, width=74, height=20)
                if node_vals and node_vals.get("ip"):
                    n_name = node_vals.get("name") or node_vals["ip"]
                    try:
                        n_port = int(node_vals.get("port") or 22)
                    except ValueError:
                        n_port = 22
                    new_node = {
                        "name": n_name,
                        "ip": node_vals["ip"],
                        "node_category": node_vals.get("role") or "server",
                        "initial_user": node_vals.get("user") or cluster_config["admin_user"],
                        "initial_password": node_vals.get("password") or "",
                        "key_file": os.path.expanduser(node_vals["key_file"]) if node_vals.get("key_file") else None,
                        "ssh_port": n_port,
                        "scenario": "key_auth" if node_vals.get("key_file") else ("password_only" if node_vals.get("password") else "existing_key"),
                        "target_user": cluster_config["ansible_user"]
                    }
                    # 一個點做完就先跑！立即探測與開門，沒有 issue 再繼續
                    res = run_node_ingestion(
                        [new_node],
                        eph_pub_text,
                        legacy_key_path=args.legacy_key,
                        non_interactive=False,
                        dialog=dialog
                    )
                    if res and res[0][2]:
                        targets.append(new_node)
                        checklist_items.append({
                            "id": n_name,
                            "name": n_name,
                            "label": f"{n_name} ({node_vals['ip']}) [✓ Verified]",
                            "desc": "Custom Added Server",
                            "checked": True
                        })
                        dialog.msgbox("Node Onboarded", f"節點 [{n_name}] ({node_vals['ip']}) 已即時完成連線探測與納管！")
                continue
            elif btn in ("Cancel", "Skip All") or selected_ids is None:
                targets = []
                break
            else:
                targets = [t for t in targets if t.get("name", t.get("ip")) in selected_ids]
                break

    ingest_results = []
    if targets:
        print(f"  • Found {C_GREEN}{len(targets)}{C_RESET} target node(s) selected for onboarding.")
    elif not args.non_interactive:
        # 互動式單節點輸入：一個點做完就先跑！
        print(f"{C_BOLD}Entering Interactive Node Registration (lab-node)...{C_RESET}")
        while True:
            t_ip = interactive_prompt("Enter Target Node IP (or 'done' to finish)", default="done")
            if t_ip.lower() in ("done", "exit", "q"):
                break
            t_user = interactive_prompt(f"Initial SSH User for {t_ip}", default=cluster_config["admin_user"])
            t_key = interactive_prompt(f"Private Key Path for {t_ip} (leave blank for password)", default="")
            t_pass = interactive_prompt(f"Initial Password for {t_user}@{t_ip} (leave blank if key used)", default="", is_secret=True)
            t_port_s = interactive_prompt(f"SSH Port for {t_ip}", default="22")
            try:
                t_port = int(t_port_s)
            except ValueError:
                t_port = 22
            single_t = {
                "ip": t_ip,
                "name": t_ip,
                "initial_user": t_user,
                "initial_password": t_pass,
                "key_file": os.path.expanduser(t_key) if t_key else None,
                "ssh_port": t_port,
                "scenario": "key_auth" if t_key else ("password_only" if t_pass else "existing_key"),
                "target_user": cluster_config["ansible_user"]
            }
            # 即時執行該節點探測與開門
            print(f"  • 正在即時驗證與納管節點 {t_ip}...")
            single_res = run_node_ingestion(
                [single_t],
                eph_pub_text,
                legacy_key_path=args.legacy_key,
                non_interactive=False,
                dialog=None
            )
            if single_res and single_res[0][2]:
                print(f"  {C_GREEN}[✓] 節點 {t_ip} 即時開門與納管成功！{C_RESET}\n")
                targets.append(single_t)
                ingest_results.extend(single_res)
            else:
                print(f"  {C_YELLOW}[!] 節點 {t_ip} 未成功納管或已略過。{C_RESET}\n")

    # 針對尚未於 Add Node / 互動階段即時納管之節點執行納管探測
    already_done_ips = {r[1] for r in ingest_results if r[2]}
    remaining_targets = [t for t in targets if t.get("ip") not in already_done_ips]
    if remaining_targets:
        rem_results = run_node_ingestion(
            remaining_targets,
            eph_pub_text,
            legacy_key_path=args.legacy_key,
            non_interactive=args.non_interactive,
            dialog=dialog if use_bsd_tui else None
        )
        ingest_results.extend(rem_results)
    success_count = sum(1 for r in ingest_results if r[2])
    print(f"\n  [✓] Probed & Ingested {success_count}/{len(targets)} Nodes Successfully.")

    # 僅針對成功納管之節點執行後續金鑰交接與宣告
    successful_ips = {r[1] for r in ingest_results if r[2]}
    targets = [t for t in targets if t.get("ip") in successful_ips]

    discovered_subnets, classified_groups = run_subnet_discovery_and_classification()

    # 決定正式金鑰的允許來源網段
    homelab_default = get_default_homelab_subnets()
    all_allowed = set(homelab_default.split(","))
    for s in discovered_subnets:
        all_allowed.add(s)
    final_allowed_subnets = ",".join(sorted(all_allowed))

    # 步驟 5: 再檢查與試運作 (金鑰輪替交接、握手驗證、機密注入)
    step_header(5, TOTAL_STEPS, "Post-Check, Trial Handover & Security Provisioning")
    if use_bsd_tui and targets:
        dialog = BSDDialog(title="OpenLabOps Master Operations Engine", subtitle="Key Handover")
        rot_success = [True]
        def _run_rotation(log_fn):
            ok = run_key_rotation_handover(
                targets=targets,
                ephemeral_key_path=eph_key_path,
                ephemeral_pubkey=eph_pub_text,
                allowed_from_subnets=final_allowed_subnets,
                ansible_user=cluster_config["ansible_user"],
                callback=log_fn
            )
            rot_success[0] = ok
            return ok

        dialog.progress_box(
            t("init.key_handover_title", "Permanent Key Rotation & Handover"),
            t("init.key_handover_desc", f"Rotating SSH Keys for {len(targets)} Node(s)...", count=len(targets)),
            _run_rotation
        )
        rotated_ok = rot_success[0]
    else:
        rotated_ok = run_key_rotation_handover(
            targets=targets,
            ephemeral_key_path=eph_key_path,
            ephemeral_pubkey=eph_pub_text,
            allowed_from_subnets=final_allowed_subnets,
            ansible_user=cluster_config["ansible_user"]
        )

    # 5.1 暫存匯出站點宣告並編譯渲染下游聯邦倉庫代碼至 /tmp (不污染孵化器 repo)
    manifest_tmp_out = export_site_manifest(cluster_config)
    compiled_work_dir = init_work_dir / "compiled"
    print(f"\n  • Compiling Downstream Repositories ({cluster_config['repo_prefix']}-*)...")
    comp_cmd = [
        sys.executable, str(ENGINE_DIR / "compiler.py"),
        "--dest-prefix", f"{cluster_config['repo_prefix']}-",
        "--base-dir", str(compiled_work_dir),
        "--create-dest-dirs",
        "--manifest", str(args.manifest or manifest_tmp_out),
        "--apply"
    ]
    c_res = subprocess.run(comp_cmd, capture_output=True, text=True)
    if c_res.returncode == 0:
        print(f"    {C_GREEN}[✓] Downstream Federation Repositories compiled successfully.{C_RESET}")
    else:
        print(f"    {C_YELLOW}[!] Compiler output note: {c_res.stderr.strip()}{C_RESET}")

    # 5.2 將本次探測最新地面事實 (configs) 與安全公鑰 (secrets) 推送到 Gitea (v1 版本)
    print(f"\n  • Pushing Fresh Ground Truth (configs) & Public Keys (secrets) to Gitea...")
    push_fresh_configs_and_secrets_to_gitea(
        cluster_config=cluster_config,
        org_name=org_target,
        repo_prefix=cluster_config.get("repo_prefix", "openlab")
    )

    # 5.3 呼叫生產劇本 (deploy-ops-tools.yml) 部署工具鏈至 Console 與各受控節點
    print(f"\n  • Deploying Operations Tools Suite via deploy-ops-tools.yml...")
    ok_local, tools_out_local = deploy_ops_tools_and_configs(cluster_config, repo_prefix=cluster_config["repo_prefix"], target_hosts="localhost")
    if ok_local:
        print(f"    {C_GREEN}[✓] Operations Tools successfully deployed to Console (/usr/local/bin/{cluster_config['repo_prefix']}){C_RESET}")
    else:
        print(f"    {C_YELLOW}[!] Note: Console tools deployment: {tools_out_local.strip() if tools_out_local else ''}{C_RESET}")

    if targets:
        ok_fleet, tools_out_fleet = deploy_ops_tools_and_configs(cluster_config, repo_prefix=cluster_config["repo_prefix"], target_hosts="servers")
        if ok_fleet:
            print(f"    {C_GREEN}[✓] Operations Tools successfully deployed to Fleet Servers (/usr/local/bin/{cluster_config['repo_prefix']}){C_RESET}")
        else:
            print(f"    {C_YELLOW}[!] Note: Fleet tools deployment: {tools_out_fleet.strip() if tools_out_fleet else ''}{C_RESET}")

    # 5.4 宣告式本機組態初始化 (/usr/local/etc/{cluster}/conf/backup.yml)
    local_cfg = Path(f"/usr/local/etc/{cluster_config['repo_prefix']}/conf/backup.yml")
    rendered_cfg = compiled_work_dir / f"{cluster_config['repo_prefix']}-configs" / "conf" / "backup_profiles.yml"
    if not rendered_cfg.exists():
        rendered_cfg = OPS_DIR / "conf" / "backup_profiles.yml"
    if not rendered_cfg.exists():
        rendered_cfg = OPS_DIR.parent / f"{cluster_config['repo_prefix']}-configs" / "conf" / "backup_profiles.yml"
    if rendered_cfg.exists() and (os.access("/usr/local/etc", os.W_OK) or os.getuid() == 0):
        try:
            local_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rendered_cfg, local_cfg)
            print(f"    {C_GREEN}[✓] Initialized local config: {local_cfg}{C_RESET}")
        except Exception as e:
            print(f"    {C_YELLOW}[!] Could not initialize {local_cfg}: {e}{C_RESET}")

    # 若有啟用 GitHub，自動將 GH_TOKEN 登記為組織 Actions Secret
    if cluster_config.get("github_enabled") and cluster_config.get("github_token"):
        print(f"\n  • Registering GitHub Token (GH_TOKEN) into Gitea Actions Secrets...")
        ok, detail = provision_github_secret_to_gitea(
            gitea_url=cluster_config.get("gitea_url", "http://gitea.lab:3000"),
            gitea_user=cluster_config.get("gitea_user", "labadmin"),
            gitea_password=cluster_config.get("gitea_password", "labtest123"),
            org_or_user=cluster_config.get("org", cluster_config.get("cluster_name", "OpenLabOps")),
            token=cluster_config["github_token"]
        )
        if ok:
            print(f"  {C_GREEN}[✓] GH_TOKEN successfully registered to Gitea Actions Secrets ({detail}){C_RESET}")
        else:
            print(f"  {C_YELLOW}[!] Note: {detail}. Ensure Gitea service is accessible.{C_RESET}")

    # 5.5 Archinstall-Style 暫存站點宣告清單已於 5.1 匯出至 /tmp 工作區並推送至 Gitea configs repo

    # 步驟 6: Ready 儀表板退出
    step_header(6, TOTAL_STEPS, "Ready Dashboard & Operational Handover")
    print(f"\n{C_BOLD}{C_GREEN}══════════════════════════════════════════════════════════════════════{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}  🎉 DAY-0 INITIALIZATION COMPLETE: ALL NODES OPERATIONAL & SECURED  {C_RESET}")
    print(f"{C_BOLD}{C_GREEN}══════════════════════════════════════════════════════════════════════{C_RESET}")
    print(f"  • Cluster Name          : {cluster_config['cluster_name']}")
    print(f"  • Ansible User          : {cluster_config['ansible_user']}")
    print(f"  • Nodes Onboarded       : {success_count} Nodes")
    if cluster_config.get("ci_bot_token"):
        _tok = cluster_config["ci_bot_token"]
        _masked = (_tok[:6] + "..." + _tok[-4:]) if len(_tok) > 12 else "***"
        print(f"  • Gitea ci-bot Token    : {_masked}")
        print(f"  • Gitea Token Storage   : /usr/local/bin/{cluster_config.get('repo_prefix', 'openlab')}/.gitea_token (mode 0600)")
    print(f"  • Permanent Key Options : from=\"{final_allowed_subnets}\"")
    if cluster_config.get("github_enabled"):
        print(f"  • GitHub Management     : Linked (Owner: {cluster_config.get('github_owner')}, Secret: GH_TOKEN)")
    else:
        print(f"  • GitHub Management     : Pure Air-Gapped (Not Linked)")
    print(f"  • Ephemeral Bootstrap   : Cleaned Up (Zero Residual)")
    print(f"{C_BOLD}{C_GREEN}══════════════════════════════════════════════════════════════════════{C_RESET}\n")

    sys.exit(0 if rotated_ok else 1)


if __name__ == "__main__":
    main()
