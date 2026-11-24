#!/usr/bin/env python3
"""
OpenLabOps Core Library: Gitea Action Dispatcher (Python Version)
"""

import os
import time
import json
import getpass
import subprocess
import urllib.request
import urllib.error
from .ui_theme import ui_info, ui_success, ui_error, ui_warn, ui_header, ui_kv, ui_divider

from .config import (
    get_gitea_url,
    get_repo_owner,
    get_token_file,
    get_repo_name,
    get_git_origin_info,
    get_cluster_prefix,
    get_admin_user,
    get_ansible_user,
    get_cluster_name,
)

GITEA_URL = get_gitea_url()
REPO_OWNER = get_repo_owner()
ACTION_REPO = get_repo_name("workflows")
TOKEN_FILE = get_token_file()

_token_cache = ""  # 僅存在於本次程序記憶體
_last_dispatch_info = {}  # 紀錄最近一次成功派發的 (owner, repo, run_id)


def load_gitea_token() -> str:
    """讀取並檢驗 Gitea Token（優先使用環境變數、其次讀取標準 TOKEN_FILE、其次使用者家目錄 ~/.gitea_token）"""
    global _token_cache
    if _token_cache:
        return _token_cache

    env_token = os.environ.get("GITEA_TOKEN")
    if env_token:
        _token_cache = env_token.strip()
        return _token_cache

    candidates = [
        TOKEN_FILE,
        os.path.expanduser("~/.gitea_token"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.R_OK):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                if token:
                    _token_cache = token
                    return token
            except Exception:
                continue

    ui_error(f"找不到或無權限讀取 Gitea Token (曾嘗試: {TOKEN_FILE}, ~/.gitea_token)")
    return ""


def _resolve_owner_repo(action_repo: str = None, owner: str = None) -> tuple:
    """解析 owner 與 repo，支援 'owner/repo' 格式或分開傳入"""
    if action_repo and "/" in action_repo:
        parts = action_repo.split("/", 1)
        return parts[0], parts[1]
    return (owner or REPO_OWNER), (action_repo or ACTION_REPO)


def get_action_runs(action_repo: str = None, page: int = 1, limit: int = 10, silent: bool = False, owner: str = None) -> dict:
    """
    查詢 Gitea Actions 歷史與執行狀態
    """
    token = load_gitea_token()
    if not token:
        return {}

    r_owner, target_repo = _resolve_owner_repo(action_repo, owner)
    api_endpoint = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/actions/runs?page={page}&limit={limit}"

    req = urllib.request.Request(
        api_endpoint,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/json",
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            return {}
    except urllib.error.HTTPError as e:
        if not silent:
            body = e.read().decode("utf-8", errors="ignore")
            ui_error(f"查詢 Action 運行紀錄失敗 (HTTP {e.code}): {body}")
        return {}
    except urllib.error.URLError as e:
        if not silent:
            ui_error(f"無法連線至 Gitea 伺服器 [{GITEA_URL}] ({e.reason})")
        return {}
    except Exception as e:
        if not silent:
            ui_error(f"查詢 Action 運行紀錄異常: {e}")
        return {}


def get_run_detail(run_id: int, action_repo: str = None, owner: str = None) -> dict:
    """
    取得特定 Action Run 之詳細執行狀態與結果
    """
    token = load_gitea_token()
    if not token:
        return {}

    r_owner, target_repo = _resolve_owner_repo(action_repo, owner)
    api_endpoint = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/actions/runs/{run_id}"

    req = urllib.request.Request(
        api_endpoint,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/json",
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            return {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        ui_error(f"查詢 Action Run #{run_id} 失敗 (HTTP {e.code}): {body}")
        return {}
    except Exception as e:
        ui_error(f"查詢 Action Run #{run_id} 異常: {e}")
        return {}


def get_run_jobs(run_id: int, action_repo: str = None, owner: str = None) -> list:
    """取得特定 Action Run 下的所有 Jobs 清單"""
    token = load_gitea_token()
    if not token:
        return []
    r_owner, target_repo = _resolve_owner_repo(action_repo, owner)
    url = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/actions/runs/{run_id}/jobs"
    req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("jobs", [])
    except Exception:
        pass
    return []


def get_job_logs(job_id: int, action_repo: str = None, owner: str = None) -> str:
    """取得特定 Job 的執行日誌"""
    token = load_gitea_token()
    if not token:
        return ""
    r_owner, target_repo = _resolve_owner_repo(action_repo, owner)
    url = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/actions/jobs/{job_id}/logs"
    req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def extract_error_snippet(log_text: str, max_lines: int = 15) -> list:
    """
    從 Action 執行日誌中精準分析並提取核心出錯行 (Root Cause Error Lines)
    排除容器建立/清理與通用結尾等系統無關資訊
    """
    if not log_text:
        return []
    lines = [l.strip() for l in log_text.splitlines() if l.strip()]
    clean_lines = []
    for l in lines:
        if len(l) > 30 and l[4] == '-' and l[7] == '-' and l[10] == 'T' and l[19] == '.':
            parts = l.split('Z ', 1)
            clean_lines.append(parts[1] if len(parts) > 1 else l)
        else:
            clean_lines.append(l)

    ignored_keywords = [
        'cleaning up container', 'removed container', 'docker volume rm',
        'job failed', "job '", 'workflow prepared', 'be triggered by event',
        'evaluation result :', '::group::', '::endgroup::'
    ]

    error_indices = []
    for idx, line in enumerate(clean_lines):
        lower = line.lower()
        if any(ign in lower for ign in ignored_keywords):
            continue
        if any(kw in lower for kw in [
            'fatal', 'error', 'failed', 'failure', 'exitcode', 'traceback',
            'exception', 'refused', 'denied', 'cannot', 'could not',
            'not found', 'unreachable', 'failed:', 'fatal:'
        ]):
            error_indices.append(idx)

    if error_indices:
        focus_idx = error_indices[-1]
        start = max(0, focus_idx - 5)
        end = min(len(clean_lines), focus_idx + 2)
        candidates = [l for l in clean_lines[start:end] if not any(ign in l.lower() for ign in ignored_keywords)]
        return candidates if candidates else clean_lines[start:end]
    else:
        meaningful = [l for l in clean_lines if not any(ign in l.lower() for ign in ignored_keywords)]
        return meaningful[-max_lines:] if len(meaningful) > max_lines else meaningful


def display_run_error_feedback(run_id: int, action_repo: str = None, owner: str = None):
    """診斷並自動輸出 Action Run 失敗之 Job、Step 與核心日誌錯誤反饋"""
    ui_header(f"🚨 Gitea Action Run #{run_id} 錯誤診斷與日誌反饋")
    jobs = get_run_jobs(run_id, action_repo, owner=owner)
    if not jobs:
        ui_warn("無法取得該 Action Run 之 Jobs 清單，請直接前往 Gitea Web UI 查看。")
        return

    failed_jobs = [j for j in jobs if j.get("conclusion") == "failure" or j.get("status") == "failure"]
    if not failed_jobs:
        failed_jobs = jobs

    for job in failed_jobs:
        job_id = job.get("id")
        job_name = job.get("name", "Unknown Job")
        ui_kv("失敗 Job", f"{job_name} (ID: {job_id})")

        steps = job.get("steps", [])
        failed_steps = [s for s in steps if s.get("conclusion") == "failure"]
        if failed_steps:
            for s in failed_steps:
                ui_kv("  └─ 失敗 Step", f"❌ {s.get('name')} (Conclusion: {s.get('conclusion')})")
        else:
            ui_kv("  └─ 狀態", "Job 執行異常中斷")

        log_text = get_job_logs(job_id, action_repo, owner=owner)
        if log_text:
            error_snippet = extract_error_snippet(log_text)
            if error_snippet:
                print("\n  🔍 [核心錯誤日誌摘錄 (Root Cause)]:")
                for line in error_snippet:
                    print(f"     \033[31m{line}\033[0m")
                print()
        else:
            ui_warn(f"無法取得 Job #{job_id} 之執行日誌。")
    ui_divider()


def gitea_dispatch(
    workflow_file: str,
    payload: dict = None,
    action_repo: str = None,
    wait: bool = True,
    timeout: int = 180
) -> bool:
    """
    呼叫 Gitea Workflow Dispatch API，預設即時追蹤執行狀態 (wait=True)。
    所有參數 (org, admin_user, ansible_user, repo_prefix) 均動態對齊 lab-init 與 Manifest 規格 [INV-03, INV-07]。
    若 Action 執行出錯 (Action Error)，將自動診斷並反饋具體錯誤訊息與日誌！
    """
    if not workflow_file:
        ui_error("未指定 workflow 檔案名稱 (例如: rotate-ansible-keys.yml)")
        return False

    token = load_gitea_token()
    if not token:
        return False

    # 1. 動態讀取由 lab-init 收集並落地於 Manifest / Config 之站點與組織參數
    org_owner = get_repo_owner()
    admin_user = get_admin_user()
    git_owner, git_repo = get_git_origin_info()
    prefix = get_cluster_prefix()
    target_repo = action_repo or get_repo_name("workflows")

    if payload is None:
        payload = {"ref": "main"}

    primary_ref = payload.get("ref", "main")
    alt_refs = [primary_ref] + [r for r in ["main", "master"] if r != primary_ref]

    # 2. 候選探測清單 (動態優先級：宣告組織 ➔ 管理員帳號 ➔ Git Remote Origin)
    candidate_targets = []
    seen = set()

    def add_candidate(o, r, ref_name, wf):
        if not o or not r or not wf:
            return
        key = (o, r, ref_name, wf)
        if key not in seen:
            seen.add(key)
            candidate_targets.append((o, r, ref_name, wf))

    candidate_owners = []
    for o in [org_owner, admin_user, git_owner]:
        if o and o not in candidate_owners:
            candidate_owners.append(o)

    candidate_repos = []
    for r in [action_repo, target_repo, f"{prefix}-workflows", f"{prefix}-operations", git_repo]:
        if r and r not in candidate_repos:
            candidate_repos.append(r)
    # 若在歷史綠色基準庫過渡期，補充舊版 homelab 命名 [INV-08]
    if prefix == "openlab" and "openlab-workflows" not in candidate_repos:
        candidate_repos.append("openlab-workflows")

    # 3. 依據站點宣告之運維角色帳號與前綴動態生成別名相容候選 (零靜態寫死)
    wf_candidates = [workflow_file]
    ans_u = get_ansible_user()
    if workflow_file == "rotate-ansible-keys.yml" and ans_u != "ansible":
        wf_candidates.append(f"rotate-{ans_u}-keys.yml")
    elif workflow_file == "rotate-storage-keys.yml" and prefix != "openlab":
        wf_candidates.append(f"rotate-{prefix}-keys.yml")
    elif workflow_file == "rotate-git-keys.yml" and prefix != "openlab":
        wf_candidates.append(f"rotate-git-{prefix}-keys.yml")
    elif workflow_file == "deploy-ops-tools.yml" and prefix != "openlab":
        wf_candidates.append(f"deploy-{prefix}-tools.yml")

    for o in candidate_owners:
        for r in candidate_repos:
            for ref_name in alt_refs:
                for wf in wf_candidates:
                    add_candidate(o, r, ref_name, wf)

    ui_info(f"正在向 Gitea 派發工作流: {workflow_file}...")

    dispatch_ok = False
    last_err = ""
    winning_owner = org_owner
    winning_repo = target_repo
    winning_wf = workflow_file
    pre_latest_id = 0
    pre_runs_cache = {}

    for c_owner, c_repo, c_ref, c_wf in candidate_targets:
        if wait and (c_owner, c_repo) not in pre_runs_cache:
            try:
                pre_runs = get_action_runs(c_repo, owner=c_owner, page=1, limit=5, silent=True).get("workflow_runs", [])
                pre_runs_cache[(c_owner, c_repo)] = max([r.get("id", 0) for r in pre_runs], default=0) if pre_runs else 0
            except Exception:
                pre_runs_cache[(c_owner, c_repo)] = 0

        cur_payload = dict(payload)
        cur_payload["ref"] = c_ref
        api_endpoint = f"{GITEA_URL}/api/v1/repos/{c_owner}/{c_repo}/actions/workflows/{c_wf}/dispatches"
        data = json.dumps(cur_payload).encode("utf-8")
        req = urllib.request.Request(
            api_endpoint,
            data=data,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in (200, 204):
                    dispatch_ok = True
                    winning_owner = c_owner
                    winning_repo = c_repo
                    winning_wf = c_wf
                    target_repo = c_repo
                    pre_latest_id = pre_runs_cache.get((c_owner, c_repo), 0)
                    if (c_owner, c_repo) != (org_owner, target_repo) or c_wf != workflow_file or c_ref != primary_ref:
                        ui_info(f"（已自動對齊目標: {c_owner}/{c_repo}@{c_ref}，工作流: {c_wf}）")
                    break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            msg = body
            try:
                err_json = json.loads(body)
                msg = err_json.get("message", body)
            except Exception:
                pass
            last_err = f"[{c_owner}/{c_repo}@{c_ref}:{c_wf}] HTTP {e.code}: {msg}"
            if e.code in (403, 404, 422):
                # 403 (無權限), 404 (倉庫/工作流不存在), 422 (分支不存在) 時繼續探測下一個候選
                continue
            ui_error(f"API 派發失敗！HTTP 狀態碼: {e.code}")
            ui_error(f"錯誤訊息: {msg}")
            return False
        except urllib.error.URLError as e:
            ui_error(f"無法連線至 Gitea 伺服器 [{GITEA_URL}] ({e.reason})")
            ui_warn("請確認 Gitea 服務是否啟動、VPN 連線是否正常，或檢查 tools.config.json / GITEA_URL 設定。")
            return False
        except Exception as e:
            ui_error(f"呼叫 Gitea API 時發生錯誤: {e}")
            return False

    if not dispatch_ok:
        ui_error(f"API 派發失敗！無法於任何候選倉庫觸發工作流 {workflow_file}")
        if last_err:
            ui_error(f"最後回傳: {last_err}")
        return False

    ui_success(f"成功觸發工作流: {winning_wf}！")

    if not wait:
        ui_info("（非阻塞模式，Gitea Runner 正在背景執行任務）")
        return True

    # 2. 等待並鎖定剛派發的 Run ID
    ui_info("⏳ 正在等待 Gitea Runner 接單排程...")
    target_run_id = None
    for _ in range(15):  # 最多約 18 秒探測新任務生成
        time.sleep(1.2)
        try:
            current_runs = get_action_runs(winning_repo, owner=winning_owner, page=1, limit=5, silent=True).get("workflow_runs", [])
            for r in current_runs:
                if r.get("id", 0) > pre_latest_id:
                    target_run_id = r.get("id")
                    break
        except Exception:
            pass
        if target_run_id:
            break

    if not target_run_id:
        ui_warn("工作流已成功派發，但未能即時鎖定新 Action Run ID（Runner 隊列可能稍有延遲）。")
        ui_info("可透過 `lab-tools` 選項查看 Gitea Actions 歷史紀錄。")
        return True

    ui_info(f"偵測到 Action Run #{target_run_id} 已啟動，開始追蹤執行狀態...")
    _last_dispatch_info.clear()
    _last_dispatch_info.update({"owner": winning_owner, "repo": winning_repo, "run_id": target_run_id})

    # 3. 追蹤 Action 執行進度，直至完成或逾時
    start_time = time.time()
    last_status = ""
    while time.time() - start_time < timeout:
        detail = get_run_detail(target_run_id, winning_repo, owner=winning_owner)
        status = detail.get("status", "unknown")
        conclusion = detail.get("conclusion", "")

        elapsed = int(time.time() - start_time)
        if status != last_status:
            ui_info(f"Action Run #{target_run_id} 當前狀態: [{status.upper()}] (已耗時 {elapsed}s)")
            last_status = status

        if status == "completed":
            if conclusion == "success":
                ui_success(f"🎉 Gitea Action Run #{target_run_id} 執行成功！(總耗時: {elapsed}s)")
                return True
            else:
                ui_error(f"❌ Gitea Action Run #{target_run_id} 執行失敗！結論: [{conclusion.upper()}] (總耗時: {elapsed}s)")
                # 自動反饋錯誤訊息、出錯步驟與核心日誌！
                display_run_error_feedback(target_run_id, winning_repo, owner=winning_owner)
                return False

        time.sleep(2.0)

    ui_warn(f"追蹤 Action Run #{target_run_id} 逾時 ({timeout}s)，任務仍在背景執行中。")
    return False


def fetch_repo_raw(repo: str, file_path: str, owner: str = None) -> str:
    """透過 Gitea API 下載指定倉庫之 Raw 檔案內容"""
    token = load_gitea_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    r_owner, target_repo = _resolve_owner_repo(repo, owner)
    api_url = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/raw/{file_path}"
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8")
    except Exception:
        pass
    return ""


def list_repo_contents(repo: str, dir_path: str = "", owner: str = None) -> list:
    """透過 Gitea API 列出指定倉庫與目錄內容清單"""
    token = load_gitea_token()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r_owner, target_repo = _resolve_owner_repo(repo, owner)
    url_path = f"/{dir_path}" if dir_path else ""
    api_url = f"{GITEA_URL}/api/v1/repos/{r_owner}/{target_repo}/contents{url_path}"
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return []


def fetch_remote_node_facts() -> tuple:
    """
    自 Gitea 聯邦倉庫 (configs/node-information 與 operations/conf/nodes) 動態抓取已納管節點事實。
    回傳 (nodes_list, source_label, is_online)。
    """
    nodes_by_host = {}
    sources = []
    is_online = False

    token = load_gitea_token()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"

    # 探測 Gitea API 連線狀態
    try:
        req = urllib.request.Request(f"{GITEA_URL}/api/v1/version", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                is_online = True
    except Exception:
        return [], "", False

    configs_repo = get_repo_name("configs")
    if configs_repo:
        entries = list_repo_contents(configs_repo, "node-information")
        if isinstance(entries, list):
            for entry in entries:
                name = entry.get("name", "") if isinstance(entry, dict) else ""
                if name.startswith("node_") and name.endswith(".json"):
                    raw = fetch_repo_raw(configs_repo, f"node-information/{name}")
                    if raw:
                        try:
                            data = json.loads(raw)
                            h = data.get("hostname") or name[5:-5]
                            nodes_by_host[h] = data
                        except Exception:
                            continue
            if nodes_by_host:
                sources.append(f"{configs_repo}/node-information")

    ops_repo = get_repo_name("operations")
    if ops_repo:
        entries = list_repo_contents(ops_repo, "conf/nodes")
        if isinstance(entries, list):
            added_ops = False
            for entry in entries:
                name = entry.get("name", "") if isinstance(entry, dict) else ""
                if name.endswith(".json") and name != "current.json":
                    h = name[:-5]
                    if h not in nodes_by_host:
                        raw = fetch_repo_raw(ops_repo, f"conf/nodes/{name}")
                        if raw:
                            try:
                                data = json.loads(raw)
                                nodes_by_host[data.get("hostname", h)] = data
                                added_ops = True
                            except Exception:
                                continue
            if added_ops:
                sources.append(f"{ops_repo}/conf/nodes")

    if not nodes_by_host:
        runner_nodes, runner_src = fetch_node_facts_via_runner()
        if runner_nodes:
            return runner_nodes, runner_src, is_online

    return list(nodes_by_host.values()), ", ".join(sources), is_online


def fetch_node_facts_via_runner(timeout: int = 45) -> tuple:
    """
    透過 ci-bot 派發 fetch-node-inventory.yml，由 Gitea Act Runner 檢出 configs/operations
    並自 Job Log 邊界標記擷取最新節點事實 JSON 陣列（維持 ci-bot RBAC 隔離）。
    """
    ok = gitea_dispatch("fetch-node-inventory.yml", payload={"ref": "main"}, wait=True, timeout=timeout)
    if not ok:
        return [], ""

    r_owner = _last_dispatch_info.get("owner") or REPO_OWNER
    r_repo = _last_dispatch_info.get("repo") or f"{get_cluster_prefix()}-workflows"
    run_id = _last_dispatch_info.get("run_id")
    if not run_id:
        runs = get_action_runs(r_repo, owner=r_owner, page=1, limit=5, silent=True).get("workflow_runs", [])
        if not runs:
            return [], ""
        run_id = runs[0].get("id")
    if not run_id:
        return [], ""

    jobs = get_run_jobs(run_id, r_repo, owner=r_owner)
    for job in jobs:
        logs = get_job_logs(job.get("id"), r_repo, owner=r_owner)
        if "===OPENLAB_NODE_LIST_START===" in logs and "===OPENLAB_NODE_LIST_END===" in logs:
            seg = logs.split("===OPENLAB_NODE_LIST_START===")[-1].split("===OPENLAB_NODE_LIST_END===")[0]
            s_idx = seg.find("[")
            e_idx = seg.rfind("]")
            if s_idx != -1 and e_idx != -1:
                try:
                    data = json.loads(seg[s_idx:e_idx + 1])
                    if isinstance(data, list):
                        return data, f"{r_owner}/{r_repo} (Runner #{run_id})"
                except Exception:
                    pass
    return [], ""


def register_node_fact_via_runner(hostname: str, node_facts: dict = None, action: str = "upsert", wait: bool = True) -> bool:
    """
    透過 ci-bot 派發 register-node-fact.yml，由 Gitea Act Runner 將節點事實寫入或移除出 *-configs / *-operations。
    """
    import base64
    b64_payload = ""
    if action != "remove" and isinstance(node_facts, dict):
        b64_payload = base64.b64encode(json.dumps(node_facts, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return gitea_dispatch(
        "register-node-fact.yml",
        payload={
            "ref": "main",
            "inputs": {
                "action": action,
                "hostname": str(hostname),
                "node_json_b64": b64_payload,
            },
        },
        wait=wait,
    )


