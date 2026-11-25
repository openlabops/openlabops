#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps 輕量 Git 倉庫遠端狀態追蹤與防呆守護工具 (lab-git-watch)
恪守 [INV-01] (100% Python 3 標準庫，零外部依賴)。

核心設計：
1. 無鎖背景抓取：使用 GIT_OPTIONAL_LOCKS=0 git fetch --quiet，不搶佔 .git/index.lock，
   讓 Powerline / git status 直接顯示 ↓ behind 與 ↑ ahead，不卡頓終端機。
2. 嚴格防呆停機 (HOLD)：只要偵測到未 commit (dirty)、未 push (ahead) 或分歧 (diverged)，
   立即暫停自動拉取並標記為 *_HOLD，寫入結構化狀態快取供 lab-status 中央看板高亮顯示。
3. 安全自動拉取：僅在 mode=auto_pull 且工作區完全乾淨、無 ahead 時才執行 git pull --ff-only。
"""

import os
import sys
import json
import time
import socket
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

LIB_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from core.config import get_cluster_prefix
from core.version import print_version


HOLD_STATES = {"DIRTY_HOLD", "AHEAD_HOLD", "DIRTY_AHEAD_HOLD", "DIVERGED_HOLD", "PULL_ERR"}


def _git_env() -> dict:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


def _run_git(repo_path: str, args: list, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo_path] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_git_env(),
    )


def get_config_candidates() -> list:
    prefix = get_cluster_prefix() or "openlab"
    return [
        Path(f"/etc/{prefix}/git-watch.json"),
        Path.home() / ".config" / prefix / "git-watch.json",
    ]


def get_cache_file() -> Path:
    prefix = get_cluster_prefix() or "openlab"
    run_dir = Path(f"/run/{prefix}")
    if run_dir.exists() and os.access(run_dir, os.W_OK):
        return run_dir / "git-watch.json"
    if os.geteuid() == 0:
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            return run_dir / "git-watch.json"
        except Exception:
            pass
    cache_dir = Path.home() / ".cache" / prefix
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "git-watch.json"


def discover_git_repos(explicit_paths: list = None) -> list:
    """探索本機受控 Git 倉庫與對應同步模式 (fetch_only / auto_pull)"""
    if explicit_paths:
        items = []
        for p in explicit_paths:
            rp = Path(p).expanduser().resolve()
            if (rp / ".git").exists():
                items.append({"name": rp.name, "path": str(rp), "mode": "fetch_only"})
        return items

    for cfg_path in get_config_candidates():
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                repos = data.get("repos", [])
                valid = []
                for r in repos:
                    rp = Path(r.get("path", "")).expanduser()
                    if rp.exists() and (rp / ".git").exists():
                        valid.append({
                            "name": r.get("name") or rp.name,
                            "path": str(rp.resolve()),
                            "mode": r.get("mode", "fetch_only"),
                        })
                if valid:
                    return valid
            except Exception:
                pass

    home = Path.home()
    candidates = [
        ("docker-compose", home / "docker-compose", "fetch_only"),
        ("docker-compose", Path("/root/docker-compose"), "auto_pull"),
        ("openlabops", home / "openlabops", "fetch_only"),
        ("openlabops", home / "openlabops", "fetch_only"),
        ("openlab-operations", home / "openlab-operations", "fetch_only"),
        ("openlab-workflows", home / "openlab-workflows", "fetch_only"),
        ("openlab-configs", home / "openlab-configs", "fetch_only"),
    ]
    seen = set()
    found = []
    for name, path_obj, mode in candidates:
        try:
            if not (path_obj / ".git").exists():
                continue
            resolved = str(path_obj.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append({"name": name, "path": resolved, "mode": mode})
        except Exception:
            continue
    return found


def inspect_git_repo(
    repo_path: str,
    mode: str = "fetch_only",
    name: str = "",
    do_fetch: bool = True,
    timeout: int = 15,
) -> dict:
    """檢查單一 Git 倉庫狀態並執行防呆判斷；僅在安全時執行 --ff-only pull"""
    rp = Path(repo_path)
    repo_name = name or rp.name
    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    result = {
        "name": repo_name,
        "path": str(rp),
        "branch": "unknown",
        "mode": mode,
        "state": "SYNCED",
        "dirty_count": 0,
        "ahead": 0,
        "behind": 0,
        "pulled": False,
        "fetch_ok": True,
        "error": "",
        "hold_reason": "",
        "checked_at": now_iso,
    }

    if not (rp / ".git").exists():
        result["state"] = "MISSING"
        result["fetch_ok"] = False
        result["error"] = "not a git repository"
        return result

    if do_fetch:
        try:
            f_res = _run_git(str(rp), ["fetch", "--quiet"], timeout=timeout)
            if f_res.returncode != 0:
                result["fetch_ok"] = False
                result["error"] = (f_res.stderr or f_res.stdout or "fetch failed").strip().splitlines()[0][:120]
        except Exception as exc:
            result["fetch_ok"] = False
            result["error"] = str(exc)[:120]

    try:
        br = _run_git(str(rp), ["rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        if br.returncode == 0 and br.stdout.strip():
            result["branch"] = br.stdout.strip()
    except Exception:
        pass

    try:
        st = _run_git(str(rp), ["status", "--porcelain"], timeout=5)
        if st.returncode == 0:
            dirty_lines = [l for l in st.stdout.splitlines() if l.strip()]
            result["dirty_count"] = len(dirty_lines)
    except Exception:
        pass

    try:
        lr = _run_git(str(rp), ["rev-list", "--left-right", "--count", "HEAD...@{u}"], timeout=5)
        if lr.returncode == 0 and lr.stdout.strip():
            parts = lr.stdout.strip().split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                result["ahead"] = int(parts[0])
                result["behind"] = int(parts[1])
    except Exception:
        pass

    dirty_cnt = result["dirty_count"]
    ahead = result["ahead"]
    behind = result["behind"]

    # 嚴格防呆：有任何未 commit 或未 push 一律先停下來 (HOLD)
    if dirty_cnt > 0 and ahead > 0:
        result["state"] = "DIRTY_AHEAD_HOLD"
        result["hold_reason"] = f"有 {dirty_cnt} 筆未 commit 變更且領先 {ahead} commit 未 push，已停止自動更新"
        return result
    if dirty_cnt > 0:
        result["state"] = "DIRTY_HOLD"
        result["hold_reason"] = f"有 {dirty_cnt} 筆未 commit 變更，已停止自動更新"
        return result
    if ahead > 0 and behind > 0:
        result["state"] = "DIVERGED_HOLD"
        result["hold_reason"] = f"本地領先 {ahead} 且落後 {behind} commit (分歧)，請手動整合"
        return result
    if ahead > 0:
        result["state"] = "AHEAD_HOLD"
        result["hold_reason"] = f"領先遠端 {ahead} commit 尚未 push，已停止自動更新"
        return result

    if behind > 0:
        if mode == "auto_pull":
            try:
                p_res = _run_git(str(rp), ["pull", "--ff-only", "--quiet"], timeout=timeout)
                if p_res.returncode == 0:
                    result["state"] = "AUTO_PULLED"
                    result["behind"] = 0
                    result["pulled"] = True
                else:
                    result["state"] = "PULL_ERR"
                    err_msg = (p_res.stderr or p_res.stdout or "pull --ff-only failed").strip()
                    result["error"] = err_msg.splitlines()[0][:120]
                    result["hold_reason"] = f"自動 pull --ff-only 失敗：{result['error']}"
            except Exception as exc:
                result["state"] = "PULL_ERR"
                result["error"] = str(exc)[:120]
                result["hold_reason"] = f"自動 pull 逾時或失敗：{result['error']}"
        else:
            result["state"] = "BEHIND"
        return result

    if not result["fetch_ok"]:
        result["state"] = "FETCH_ERR"
    else:
        result["state"] = "SYNCED"
    return result


def scan_all_repos(
    explicit_paths: list = None,
    do_fetch: bool = True,
    force_fetch_only: bool = False,
    force_pull: bool = False,
    write_cache: bool = True,
) -> dict:
    repos = discover_git_repos(explicit_paths)
    items = []
    for r in repos:
        mode = r.get("mode", "fetch_only")
        if force_fetch_only:
            mode = "fetch_only"
        elif force_pull:
            mode = "auto_pull"
        items.append(inspect_git_repo(r["path"], mode=mode, name=r["name"], do_fetch=do_fetch))

    payload = {
        "hostname": socket.gethostname().split(".")[0],
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "timestamp": int(time.time()),
        "repos": items,
    }
    if write_cache:
        try:
            cache_file = get_cache_file()
            tmp_file = cache_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp_file.replace(cache_file)
        except Exception:
            pass
    return payload


def main():
    parser = argparse.ArgumentParser(
        prog="lab-git-watch",
        description="OpenLabOps 輕量 Git 遠端同步追蹤與防呆守護工具",
    )
    parser.add_argument("-v", "--version", action="store_true", help="顯示版本號")
    parser.add_argument("--pull", action="store_true", help="允許對乾淨且無 ahead 的落後倉庫執行 git pull --ff-only")
    parser.add_argument("--fetch-only", action="store_true", help="強制只執行無鎖 git fetch，不進行任何 pull")
    parser.add_argument("--no-fetch", action="store_true", help="跳過遠端 fetch，僅檢查本地 dirty/ahead/behind 狀態")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式報告")
    parser.add_argument("-q", "--quiet", action="store_true", help="靜默模式（僅在發生 HOLD 防呆或錯誤時輸出）")
    parser.add_argument("paths", nargs="*", help="指定要掃描的倉庫路徑（省略則自動探索或讀取 git-watch.json）")
    args = parser.parse_args()

    if args.version:
        print_version("OpenLabOps Git Watch (lab-git-watch)")
        return

    report = scan_all_repos(
        explicit_paths=args.paths or None,
        do_fetch=not args.no_fetch,
        force_fetch_only=args.fetch_only,
        force_pull=args.pull,
        write_cache=True,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    repos = report.get("repos", [])
    has_hold = any(r["state"] in HOLD_STATES for r in repos)
    if args.quiet and not has_hold:
        return

    for r in repos:
        st = r["state"]
        tag = f"[{r['name']}:{r['branch']}]"
        if st == "SYNCED":
            print(f"  ✓ {tag} 已同步 ({r['path']})")
        elif st == "AUTO_PULLED":
            print(f"  ⬇ {tag} 已安全自動 pull --ff-only ({r['path']})")
        elif st == "BEHIND":
            print(f"  ⬇ {tag} 遠端有 {r['behind']} 個新 commit 待 pull ({r['path']})")
        elif st in HOLD_STATES:
            print(f"  ⛔ {tag} {st}: {r['hold_reason']} ({r['path']})")
        elif st == "FETCH_ERR":
            print(f"  ⚠ {tag} FETCH_ERR: {r['error']} ({r['path']})")
        else:
            print(f"  • {tag} {st} ({r['path']})")


if __name__ == "__main__":
    main()
