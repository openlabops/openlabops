#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Universal Node Boot Public Key Synchronizer (lab-boot-sync)
Governed by [INV-01] (100% Python Standard Library) & Secrets Git SHA Index Contract.

Operational Architecture:
1. Zero HTTP Key Downloads: Client nodes NEVER download raw private keys over HTTP.
2. Secrets Git SHA Index: Uses {prefix}-secrets git commit SHA as the authoritative
   version index. Reads local /etc/{prefix}/last_synced_commit and compares with
   remote {prefix}-secrets HEAD commit SHA.
3. Fast Path (Identical SHA): If local SHA equals remote HEAD SHA,
   keys are up-to-date. Releases lockout immediately (/run/{prefix}/synced_ok).
4. Gitea Action Dispatch: If SHA differs (node was offline during key rotation),
   triggers deploy-ssh-keys.yml via Gitea API with target_hosts, source_commit_sha,
   and deploy_client_keys=false (strictly compliant with INV-02).
5. Roll-Forward Sync: Action uses historical key corresponding to source_commit_sha
   to authenticate, pushes latest public key, purges old key by comment, and updates
   local /etc/{prefix}/last_synced_commit without generating new key pairs.
"""

import os
import sys
import time
import socket
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.config import get_gitea_url, get_repo_owner, get_cluster_prefix, get_ansible_user
from core.gitea_api import load_gitea_token, gitea_dispatch
from core.lockout import get_sync_stamp_file
from core.i18n import t
from core.version import get_local_version

SYNC_STAMP_FILE = Path("/run/openlab/synced_ok")
LOCAL_COMMIT_FILE = Path("/etc/openlab/last_synced_commit")


def get_current_hostname() -> str:
    return socket.gethostname().split(".")[0].lower()


def get_commit_file_path() -> Path:
    if LOCAL_COMMIT_FILE and str(LOCAL_COMMIT_FILE) != "/etc/openlab/last_synced_commit" and str(LOCAL_COMMIT_FILE) != "/etc/openlab/last_synced_commit":
        return LOCAL_COMMIT_FILE
    prefix = get_cluster_prefix() or "openlab"
    return Path(f"/etc/{prefix}/last_synced_commit")


def get_last_synced_commit() -> str:
    """取得節點本地記錄之上次同步 secrets Git Commit SHA"""
    commit_file = get_commit_file_path()
    if commit_file.exists():
        try:
            content = commit_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass
    return ""


def update_local_synced_commit(commit_sha: str) -> bool:
    """在節點本地 /etc/{prefix}/last_synced_commit 更新已同步之 Commit SHA"""
    commit_file = get_commit_file_path()
    try:
        commit_file.parent.mkdir(parents=True, exist_ok=True)
        commit_file.write_text(f"{commit_sha.strip()}\n", encoding="utf-8")
        return True
    except Exception as e:
        sys.stderr.write(f"Warning: Could not update {commit_file}: {e}\n")
        return False


def get_remote_head_commit(gitea_url: str = "", org: str = "", repo_prefix: str = "") -> str:
    """以 {repo_prefix}-secrets 的 Git Commit 作為權威索引，查詢遠端最新 HEAD Commit SHA"""
    url = (gitea_url or get_gitea_url()).rstrip("/")
    owner = org or get_repo_owner()
    prefix = repo_prefix or get_cluster_prefix() or "openlab"
    token = load_gitea_token()
    headers = {"User-Agent": f"{prefix}-boot-sync"}
    if token:
        headers["Authorization"] = f"token {token}"

    for repo_suffix in ["secrets", "workflows", "operations"]:
        repo_name = f"{prefix}-{repo_suffix}"
        for branch in ["main", "master"]:
            api_url = f"{url}/api/v1/repos/{owner}/{repo_name}/branches/{branch}"
            req = urllib.request.Request(api_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sha = data.get("commit", {}).get("id", "").strip()
                    if sha:
                        return sha
            except Exception:
                continue
    return ""


def release_lockout(commit_sha: str) -> None:
    """寫入同步成功戳記，解除門禁鎖定"""
    stamp_file = get_sync_stamp_file()
    try:
        stamp_file.parent.mkdir(parents=True, exist_ok=True)
        stamp_file.write_text(f"synced_sha={commit_sha}\ntimestamp={int(time.time())}\n", encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Warning: Could not write sync stamp {stamp_file}: {e}\n")


def clear_lockout() -> None:
    """清除同步成功戳記，進入鎖定狀態"""
    stamp_file = get_sync_stamp_file()
    try:
        stamp_file.unlink(missing_ok=True)
    except Exception:
        pass


def dispatch_key_sync(target_host: str, target_user: str = "", source_sha: str = "", wait: bool = False, timeout: int = 120) -> bool:
    """透過 Gitea Actions 觸發金鑰同步劇本 (嚴格恪守 INV-02: deploy_client_keys 恆為 false)"""
    prefix = get_cluster_prefix() or "openlab"
    user_val = target_user or get_ansible_user()
    payload = {
        "ref": "main",
        "inputs": {
            "target_hosts": target_host,
            "target_user": user_val,
            "source_commit_sha": source_sha or "HEAD",
            "deploy_client_keys": "false",
            "deploy_authorized_keys": "true",
            "deploy_ssh_config": "true",
        },
    }
    action_repo = f"{prefix}-workflows"
    return gitea_dispatch(
        workflow_file="deploy-ssh-keys.yml",
        payload=payload,
        action_repo=action_repo,
        wait=wait,
        timeout=timeout
    )


def dispatch_key_sync_action(target_host: str, commit_sha: str, gitea_url: str = "", org: str = "", repo_prefix: str = "") -> bool:
    """向後相容辅助介面：直接觸發遠端 Gitea Actions 金鑰同步工作流 (恪守 INV-02)"""
    if not gitea_url and not org and not repo_prefix:
        return dispatch_key_sync(target_host=target_host, source_sha=commit_sha)
    url = (gitea_url or get_gitea_url()).rstrip("/")
    owner = org or get_repo_owner()
    prefix = repo_prefix or get_cluster_prefix() or "openlab"
    token = load_gitea_token()
    workflow_id = "deploy-ssh-keys.yml"
    api_url = f"{url}/api/v1/repos/{owner}/{prefix}-workflows/actions/workflows/{workflow_id}/dispatches"

    for branch in ["main", "master"]:
        payload = {
            "ref": branch,
            "inputs": {
                "target_hosts": target_host,
                "source_commit_sha": commit_sha or "HEAD",
                "deploy_client_keys": "false",
                "deploy_authorized_keys": "true",
                "deploy_ssh_config": "true"
            }
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"token {token}" if token else ""
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    return True
        except Exception:
            continue
    return False


def main():
    parser = argparse.ArgumentParser(
        prog="lab-boot-sync",
        description=t("boot_sync.cli_desc", "OpenLabOps Universal Node Boot Public Key Synchronizer & Lockout Guard [INV-01, INV-02]")
    )
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Boot Key Synchronizer (lab-boot-sync) v{get_local_version()}")
    parser.add_argument("-c", "--check", action="store_true", help=t("boot_sync.cli_check", "Check local vs remote Secrets Commit SHA without syncing or unlocking"))
    parser.add_argument("-f", "--force", action="store_true", help=t("boot_sync.cli_force", "Force-trigger Gitea Actions key deployment workflow"))
    parser.add_argument("-w", "--wait", action="store_true", help=t("boot_sync.cli_wait", "Wait for Gitea Actions / Ansible execution to complete before exiting"))
    parser.add_argument("--timeout", type=int, default=120, help=t("boot_sync.cli_timeout", "Wait timeout in seconds (default: 120)"))
    parser.add_argument("--target-host", default="", help=t("boot_sync.cli_target_host", "Specify target hostname to sync (default: current host)"))
    parser.add_argument("--target-user", default="", help=t("boot_sync.cli_target_user", "Specify target user (default: lab/labadmin)"))

    args = parser.parse_args()

    prefix = get_cluster_prefix() or "openlab"
    hostname = args.target_host or get_current_hostname()
    target_user = args.target_user or get_ansible_user()
    stamp_file = get_sync_stamp_file()

    print("=" * 65)
    print(f"  {prefix.upper()} Node Boot Key Synchronization Handshake")
    print("  Governed by Secrets Git SHA Index Contract [INV-01, INV-02]")
    print("=" * 65)

    local_sha = get_last_synced_commit()
    remote_sha = get_remote_head_commit()

    print(f"[•] Target Node            : {hostname}")
    print(f"[•] Target User            : {target_user}")
    print(f"[•] Local Secrets SHA      : {local_sha or 'NONE'}")
    print(f"[•] Remote Secrets HEAD SHA: {remote_sha or 'UNREACHABLE'}")

    if args.check:
        if local_sha and remote_sha and local_sha == remote_sha:
            print("  [✓] Key state is up to date (Local matches Remote).")
            sys.exit(0)
        else:
            print("  [!] Key state drift detected or unverified.")
            sys.exit(1)

    # 1. 比對 Secrets Git Commit SHA：若一致代表公鑰已是最新版
    if not args.force and local_sha and remote_sha and local_sha == remote_sha:
        print("  [✓] Local SHA matches secrets HEAD. Key state is up to date.")
        release_lockout(local_sha)
        print(f"  [✓] Node Synchronization Released. Lockout cleared: {stamp_file}")
        print("=" * 65)
        sys.exit(0)

    # 2. SHA 不一致或強制模式：向 Gitea Actions 請求金鑰部署
    if args.force:
        print("[•] Force mode requested: Dispatching Gitea Actions key synchronization...")
    else:
        print("[•] Version Drift Detected: Requesting Gitea Actions to roll-forward public key...")

    dispatched = dispatch_key_sync(
        target_host=hostname,
        target_user=target_user,
        source_sha=local_sha,
        wait=args.wait,
        timeout=args.timeout
    )

    if dispatched:
        print("  [✓] Gitea Actions key sync workflow dispatched successfully.")
        if args.wait:
            if remote_sha:
                update_local_synced_commit(remote_sha)
            release_lockout(remote_sha or local_sha or "SYNCED")
            print(f"  [✓] Node Synchronization Released. Lockout cleared: {stamp_file}")
            print("=" * 65)
            sys.exit(0)
        else:
            print("  [•] Awaiting Ansible execution to converge authorized_keys and clear lockout...")
            for _ in range(8):
                if stamp_file.exists():
                    if remote_sha:
                        update_local_synced_commit(remote_sha)
                    print(f"\n[✓] Node Synchronization Released. Lockout cleared: {stamp_file}")
                    print("=" * 65)
                    sys.exit(0)
                time.sleep(2)

            print("  [!] Notice: Workflow dispatched. Node remains locked until Ansible completes.")
            sys.exit(0)
    else:
        print("  [!] Notice: Could not contact Gitea API or offline; lockout remains strictly active.")
        clear_lockout()
        sys.exit(1)


if __name__ == "__main__":
    main()
