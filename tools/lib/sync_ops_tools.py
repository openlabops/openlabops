#!/usr/bin/env python3
"""
OpenLabOps Tool: Operations Tools Auto-Update & Installer (/usr/local/bin/openlab)
負責透過 Gitea REST API 或本地倉庫將最新維運工具鏈部署至系統目錄 /usr/local/bin/openlab/，
並自動建立標準軟連結至 /usr/local/bin/。
"""

import os
import sys
import shutil
import tarfile
import argparse
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.ui_theme import ui_header, ui_kv, ui_divider, ui_info, ui_success, ui_warn, ui_error
from core.gitea_api import load_gitea_token, GITEA_URL, REPO_OWNER
from core.version import get_local_version, get_remote_version, compare_versions, print_version

INSTALL_DIR = "/usr/local/bin/openlab"
BIN_DIR = "/usr/local/bin"

def _detect_local_workspace() -> str:
    install_resolved = Path(INSTALL_DIR).resolve()
    candidates = [
        Path.cwd() / "tools",
        Path.cwd(),
        Path(__file__).resolve().parent.parent,
        Path.home() / "openlabops" / "tools",
        Path.home() / "openlab-tools",
    ]
    for c in candidates:
        try:
            if c.resolve() == install_resolved:
                continue
        except Exception:
            pass
        if c.exists() and (c / "lib").exists():
            return str(c)
    return str(Path.home() / "openlabops" / "tools")

LOCAL_WORKSPACE = _detect_local_workspace()

SYMLINKS = [
    ("bin/lab-tools", "lab-tools"),
    ("bin/lab-status", "lab-status"),
    ("bin/lab-node", "lab-node"),
    ("bin/lab-config", "lab-config"),
    ("bin/lab-setup", "lab-setup"),
    ("bin/lab-ssh", "lab-ssh"),
    ("bin/lab-info", "lab-info"),
    ("bin/lab-backup", "lab-backup"),
    ("bin/lab-upgrade", "lab-upgrade"),
    ("bin/lab-man", "lab-man"),
    ("bin/sync-ssh-config", "sync-ssh-config"),
    ("bin/sync-ssh-keys", "sync-ssh-keys"),
    ("bin/sync-ops-tools", "sync-ops-tools"),
    ("bin/generate-host-ssh-key", "generate-host-ssh-key"),
    ("bin/revoke-host-ssh-key", "revoke-host-ssh-key"),
    ("bin/render-node-doc", "render-node-doc"),
]

if os.path.exists(os.path.join(INSTALL_DIR, "bin/lab-boot-sync")):
    SYMLINKS.append(("bin/lab-boot-sync", "lab-boot-sync"))

EXPECTED_CLI_TOOLS = [name for _, name in SYMLINKS]


def update_tools_from_gitea(force: bool = False, check_only: bool = False) -> bool:
    """自 Gitea REST API 檢查版本並下載最新代碼 tarball 更新安裝目錄"""
    local_ver = get_local_version()
    remote_ver = get_remote_version()

    ui_kv("目前安裝版本", f"v{local_ver}")
    ui_kv("遠端最新版本", f"v{remote_ver}" if remote_ver else "無法連線查詢")

    if remote_ver and not force:
        cmp_res = compare_versions(local_ver, remote_ver)
        if cmp_res >= 0:
            ui_success(f"目前工具版本 (v{local_ver}) 已是最新狀態，無需更新。")
            ui_info("💡 如需強制重新安裝，請加上 --force 參數。")
            return True
        else:
            ui_info(f"🚀 偵測到新版本: v{local_ver} -> v{remote_ver}")

    if check_only:
        if remote_ver and compare_versions(local_ver, remote_ver) < 0:
            ui_warn(f"發現可用新版本 v{remote_ver}！可執行 'sync-ops-tools' 進行升級。")
            return False
        return True

    token = load_gitea_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = os.path.join(tmp_dir, "tools.tar.gz")
        downloaded = False
        last_err = None
        from core.config import get_git_origin_info, get_repo_name
        origin_owner, origin_repo = get_git_origin_info()
        ops_repo = get_repo_name("operations")
        repo_candidates = []
        if ops_repo:
            repo_candidates.append((REPO_OWNER, ops_repo, "main"))
        if origin_owner and origin_repo:
            repo_candidates.append((origin_owner, origin_repo, "master"))
            repo_candidates.append((origin_owner, origin_repo, "main"))
        for r in ("openlab-operations", "openlabops", "openlab-tools"):
            repo_candidates.append((REPO_OWNER, r, "main"))
            repo_candidates.append((REPO_OWNER, r, "master"))

        seen_urls = set()
        for owner_cand, repo_cand, branch_cand in repo_candidates:
            archive_url = f"{GITEA_URL}/api/v1/repos/{owner_cand}/{repo_cand}/archive/{branch_cand}.tar.gz"
            if archive_url in seen_urls:
                continue
            seen_urls.add(archive_url)
            ui_info(f"正在從 Gitea 下載最新工具代碼: {archive_url}")
            try:
                req = urllib.request.Request(archive_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp, open(tar_path, "wb") as out_f:
                    if resp.status == 200:
                        shutil.copyfileobj(resp, out_f)
                        downloaded = True
                        break
            except Exception as e:
                last_err = e

        try:
            if not downloaded:
                raise RuntimeError(last_err or "無法自 Gitea 下載倉庫壓縮包")
            ui_info("代碼包下載完成，正在解壓縮...")

            with tarfile.open(tar_path, "r:gz") as tar:
                try:
                    tar.extractall(path=tmp_dir, filter="data")
                except TypeError:
                    tar.extractall(path=tmp_dir)

            extracted_root = None
            for cand in ("openlab-operations", "openlabops", "openlab-tools"):
                cand_path = os.path.join(tmp_dir, cand)
                if os.path.exists(cand_path):
                    extracted_root = cand_path
                    break
            if not extracted_root:
                dirs = [d for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d))]
                if dirs:
                    extracted_root = os.path.join(tmp_dir, dirs[0])
            if extracted_root and os.path.exists(os.path.join(extracted_root, "tools", "lib")):
                extracted_root = os.path.join(extracted_root, "tools")

            install_extracted(extracted_root)
            return True
        except Exception as e:
            ui_warn(f"從 Gitea 下載失敗: {e}")
            if os.path.exists(LOCAL_WORKSPACE):
                ui_info(f"切換至本地工作區同步: {LOCAL_WORKSPACE}")
                install_extracted(LOCAL_WORKSPACE)
                return True
            return False


def install_extracted(src_root: str):
    """將來源目錄複製至 /usr/local/bin/openlab 並建立軟連結與設定權限"""
    try:
        os.makedirs(INSTALL_DIR, mode=0o755, exist_ok=True)
    except PermissionError:
        ui_error(f"寫入權限不足！安裝至 {INSTALL_DIR} 需要管理員權限，請使用 sudo 執行。")
        sys.exit(1)

    if os.path.realpath(src_root) == os.path.realpath(INSTALL_DIR):
        ui_error(f"來源路徑與安裝目錄相同 ({INSTALL_DIR})，為避免自我覆寫清除已中止操作。")
        sys.exit(1)

    tools_src = os.path.join(src_root, "tools") if os.path.isdir(os.path.join(src_root, "tools", "lib")) else src_root
    repo_root = src_root if os.path.isdir(os.path.join(src_root, "tools", "lib")) else os.path.dirname(src_root)

    try:
        for item in ["bin", "lib", "docs", "conf"]:
            s = os.path.join(tools_src, item)
            d = os.path.join(INSTALL_DIR, item)
            if os.path.exists(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)

        for extra_item in ["engine", "lang", "docs"]:
            s = os.path.join(repo_root, extra_item)
            d = os.path.join(INSTALL_DIR, extra_item)
            if os.path.exists(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)

        for stale in ["python", "script"]:
            stale_path = os.path.join(INSTALL_DIR, stale)
            if os.path.exists(stale_path):
                shutil.rmtree(stale_path)
    except PermissionError:
        ui_error(f"寫入權限不足！更新 {INSTALL_DIR} 需要管理員權限，請使用 sudo 執行。")
        sys.exit(1)

    for ver_cand in [os.path.join(tools_src, "VERSION"), os.path.join(repo_root, "VERSION")]:
        if os.path.exists(ver_cand):
            dst_ver = os.path.join(INSTALL_DIR, "VERSION")
            shutil.copy2(ver_cand, dst_ver)
            os.chmod(dst_ver, 0o644)
            break
    try:
        for comp_dir in ("lib", "engine"):
            target_comp_dir = os.path.join(INSTALL_DIR, comp_dir)
            if os.path.exists(target_comp_dir):
                subprocess.run([sys.executable, "-m", "compileall", "-f", "-q", target_comp_dir], check=False)
    except Exception:
        pass

    for root, dirs, files in os.walk(INSTALL_DIR):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o755)
            except Exception:
                pass
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, INSTALL_DIR)
            if f.startswith(".gitea_token") or f == ".gitea_token":
                os.chmod(p, 0o600)
            elif rel.startswith("bin" + os.sep) or f.endswith(".py") or f.endswith(".sh"):
                os.chmod(p, 0o755)
            else:
                os.chmod(p, 0o644)

    os.makedirs(BIN_DIR, mode=0o755, exist_ok=True)
    for src_rel, symlink_name in SYMLINKS:
        target_bin = os.path.join(BIN_DIR, symlink_name)
        source_target = os.path.join(INSTALL_DIR, src_rel)
        if os.path.exists(source_target):
            try:
                if os.path.islink(target_bin) or os.path.exists(target_bin):
                    os.remove(target_bin)
                os.symlink(source_target, target_bin)
            except Exception as e:
                ui_warn(f"無法建立軟連結 {target_bin}: {e}")

    current_v = get_local_version()
    ui_success(f"✨ 維運工具鏈已成功更新部署至 {INSTALL_DIR} (版本: v{current_v})")


def main():
    from core.i18n import t
    parser = argparse.ArgumentParser(prog="sync-ops-tools", description=t("sync_tools.cli_desc", "OpenLabOps Tools Auto-Updater & Version Manager"))
    parser.add_argument("-v", "--version", action="store_true", help=t("common.cli_version", "Show version information"))
    parser.add_argument("-n", "--node", type=str, help=t("sync_tools.cli_node", "Target node/group to deploy or update via Gitea Runner (e.g. control-node, servers)"))
    parser.add_argument("-c", "--check", action="store_true", help=t("sync_tools.cli_check", "Check for new version without writing changes"))
    parser.add_argument("-f", "--force", action="store_true", help=t("sync_tools.cli_force", "Force reinstall even if version matches"))
    parser.add_argument("-l", "--local", action="store_true", help=t("sync_tools.cli_local", "Prefer syncing from local development workspace"))
    args = parser.parse_args()

    if args.version:
        print_version("OpenLabOps Tools")
        return

    if args.node:
        ui_header("OpenLabOps Tools 遠端節點部署 (Runner Playbook)")
        ui_kv("目標節點", args.node)
        ui_kv("執行模式", "Gitea Actions CI/CD Runner (deploy-ops-tools.yml)")
        ui_divider()
        payload = {"ref": "main", "inputs": {"target_hosts": args.node}}
        from core.gitea_api import gitea_dispatch
        success = gitea_dispatch("deploy-ops-tools.yml", payload)
        if success:
            ui_success("已成功向 Gitea Actions 派發部署任務！請稍候查看執行紀錄。")
        return

    ui_header("OpenLabOps 版本管理與自動更新工具")
    ui_kv("目標安裝路徑", INSTALL_DIR)
    ui_kv("系統指令路徑", BIN_DIR)
    ui_divider()

    if args.local and os.path.exists(LOCAL_WORKSPACE):
        ui_info(f"使用本地工作區來源: {LOCAL_WORKSPACE}")
        install_extracted(LOCAL_WORKSPACE)
    else:
        update_tools_from_gitea(force=args.force, check_only=args.check)


if __name__ == "__main__":
    main()
