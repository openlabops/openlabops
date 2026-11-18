#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps / OpenLabOps Manifest Compiler & Repository Distillation Engine
1. Full Federation Synthesis (--full-federation):
   Renders templates and synchronizes the downstream repositories (homelab-*)
   using core components and site manifests. Backed up configs and keys reside
   in configs and secrets repos; ops creates the runnable GitOps environment.
2. OpenLabOps Distillation (--distill-openlab):
   Distills openlabops into openlabops as a standalone, cut-down operations hub
   (flat LAN, generic Linux, zero private-cloud appliances/mesh dependencies).
"""

import sys
import os
import json
import shutil
import difflib
import argparse
import re
import tempfile
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
OPS_DIR = ENGINE_DIR.parent
DEFAULT_BASE_DIR = OPS_DIR.parent
OPENLAB_DIR = DEFAULT_BASE_DIR / "openlabops"
DEFAULT_MANIFEST = OPS_DIR / "conf" / "openlab.manifest.yml"
if not DEFAULT_MANIFEST.exists():
    DEFAULT_MANIFEST = OPS_DIR / "conf" / "openlab.manifest.yml"
CORE_MANIFEST = OPS_DIR / "conf" / "core.manifest.yml"
TEMPLATES_DIR = OPS_DIR / "templates"

_LIB_DIR = str(OPS_DIR / "tools" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from core.yaml_parser import parse_yaml_file  # noqa: E402


def parse_simple_yaml(filepath):
    """透過共用純 Python 標準庫 YAML 解析器 (core.yaml_parser) 解析宣告檔 [INV-01]"""
    return parse_yaml_file(filepath)


def regex_replace(s, pattern, replacement):
    if s is None:
        return ""
    return re.sub(pattern, replacement, str(s))


def extract_inventory_metadata(context, ops_dir: Path):
    """
    從 manifest inventory 與 conf/nodes/*.json 動態萃取所有節點 (nodes) 與群組 (groups)。
    完全遵循標準 Ansible 抽象化變數精神，支援群組與節點展開。
    """
    groups = set()
    nodes = set()

    inv = context.get("inventory", {})

    def walk_inv(node, current_group=None):
        if not isinstance(node, dict):
            return
        if "hosts" in node and isinstance(node["hosts"], dict):
            if current_group:
                groups.add(current_group)
            for h_name in node["hosts"]:
                nodes.add(h_name)
        for k, v in node.items():
            if k in ("hosts", "vars"):
                continue
            if isinstance(v, dict):
                groups.add(k)
                walk_inv(v, current_group=k)

    walk_inv(inv)

    # 亦可納入 conf/nodes/*.json 探測到的活體節點
    nodes_dir = ops_dir / "conf" / "nodes"
    if nodes_dir.exists():
        for f in nodes_dir.glob("*.json"):
            if f.name != "current.json":
                nodes.add(f.stem)

    filtered_groups = sorted([g for g in groups if g not in ("all", "ungrouped", "servers", "appliances", "homelab")])
    if not filtered_groups:
        filtered_groups = ["servers"]

    return filtered_groups, sorted(list(nodes))


def _lookup_path(path_str: str, ctx: dict):
    """在上下文中查找點號路徑或字串字面量，支援 + 字串串接與 .items()"""
    path_str = path_str.strip()
    if "+" in path_str and not (path_str.startswith('"') or path_str.startswith("'")):
        segs = [s.strip() for s in path_str.split("+")]
        return "".join(str(_lookup_path(s, ctx) or "") for s in segs)
    if (path_str.startswith('"') and path_str.endswith('"')) or (path_str.startswith("'") and path_str.endswith("'")):
        return path_str[1:-1]
    if path_str.endswith(".items()"):
        obj = _lookup_path(path_str[:-8], ctx)
        return list(obj.items()) if isinstance(obj, dict) else []
    cur = ctx
    for seg in path_str.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return None
    return cur


def _split_top_level_pipes(expr: str):
    parts = []
    cur = []
    depth = 0
    in_quote = None
    for ch in expr:
        if in_quote:
            cur.append(ch)
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
                cur.append(ch)
            elif ch == "(":
                depth += 1
                cur.append(ch)
            elif ch == ")":
                depth = max(0, depth - 1)
                cur.append(ch)
            elif ch == "|" and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def _stdlib_eval_expr(expr: str, ctx: dict):
    """純標準庫評估模板表達式 (支援行內 if/else 三元運算、點號屬性存取、default、lower、capitalize、upper、regex_replace)"""
    expr = expr.strip()
    m_ternary = re.match(r"^(.*?)\s+if\s+(.*?)\s+else\s+(.*)$", expr)
    if m_ternary:
        true_expr, cond_expr, false_expr = m_ternary.group(1).strip(), m_ternary.group(2).strip(), m_ternary.group(3).strip()
        if _eval_condition(cond_expr, ctx):
            return _stdlib_eval_expr(true_expr, ctx)
        return _stdlib_eval_expr(false_expr, ctx)

    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1].strip()

    parts = _split_top_level_pipes(expr)
    val = _lookup_path(parts[0], ctx)
    for flt in parts[1:]:
        if flt == "lower" and val is not None:
            val = str(val).lower()
        elif flt == "capitalize" and val is not None:
            val = str(val).capitalize()
        elif flt == "upper" and val is not None:
            val = str(val).upper()
        elif flt.startswith("default(") and flt.endswith(")"):
            if val is None or val == "":
                def_arg = flt[8:-1].strip()
                val = _stdlib_eval_expr(def_arg, ctx) if "|" in def_arg else _lookup_path(def_arg, ctx)
        elif flt.startswith("regex_replace(") and flt.endswith(")"):
            inner = flt[14:-1]
            args = [a.strip().strip('"\'') for a in inner.split(",", 1)]
            if len(args) == 2 and val is not None:
                pattern = args[0].replace("\\\\", "\\")
                val = regex_replace(val, pattern, args[1])
    return "" if val is None else str(val)


def _eval_condition(cond_str: str, ctx: dict) -> bool:
    """純標準庫評估 {% if ... %} 條件表達式 (支援 and, or, is defined, is mapping, is iterable, ==, !=)"""
    cond_str = cond_str.strip()
    if " or " in cond_str:
        return any(_eval_condition(part, ctx) for part in cond_str.split(" or "))
    if " and " in cond_str:
        return all(_eval_condition(part, ctx) for part in cond_str.split(" and "))
    if cond_str.endswith(" is not defined"):
        var_path = cond_str[:-15].strip()
        return _lookup_path(var_path, ctx) is None
    if cond_str.endswith(" is defined"):
        var_path = cond_str[:-11].strip()
        return _lookup_path(var_path, ctx) is not None
    if cond_str.endswith(" is not mapping"):
        var_path = cond_str[:-15].strip()
        return not isinstance(_lookup_path(var_path, ctx), dict)
    if cond_str.endswith(" is mapping"):
        var_path = cond_str[:-11].strip()
        return isinstance(_lookup_path(var_path, ctx), dict)
    if cond_str.endswith(" is iterable"):
        var_path = cond_str[:-12].strip()
        val = _lookup_path(var_path, ctx)
        return isinstance(val, (list, tuple, dict, set))
    if "==" in cond_str:
        lhs, rhs = cond_str.split("==", 1)
        lval = _lookup_path(lhs, ctx)
        rval = _lookup_path(rhs, ctx)
        if lval is None or rval is None:
            return False
        return str(lval) == str(rval)
    if "!=" in cond_str:
        lhs, rhs = cond_str.split("!=", 1)
        lval = _lookup_path(lhs, ctx)
        rval = _lookup_path(rhs, ctx)
        if lval is None and rval is None:
            return False
        if lval is None or rval is None:
            return True
        return str(lval) != str(rval)
    val = _lookup_path(cond_str, ctx)
    return bool(val)


_TOKEN_RE = re.compile(r"(\{%-?\s*.*?\s*-?%\}|\{\{\s*.*?\s*\}\})", re.DOTALL)


def _stdlib_render_j2(template_str: str, ctx: dict) -> str:
    """100% Python 標準庫實現之輕量級模板渲染器 (支援 raw, if/elif/else/endif, for/endfor, {{ }}) [INV-01]"""
    raw_blocks = []

    def _save_raw(m):
        raw_blocks.append(m.group(1))
        return f"__RAW_BLOCK_{len(raw_blocks) - 1}__"

    s = re.sub(r"\{%-?\s*raw\s*-?%\}(.*?)\{%-?\s*endraw\s*-?%\}", _save_raw, template_str, flags=re.DOTALL)
    tokens = _TOKEN_RE.split(s)

    # Normalize whitespace control tags ({%- and -%})
    for i, tok in enumerate(tokens):
        if tok.startswith("{%-") and i > 0:
            tokens[i - 1] = re.sub(r"[ \t]*\r?\n[ \t]*$", "", tokens[i - 1])
        if tok.endswith("-%}") and i + 1 < len(tokens):
            tokens[i + 1] = re.sub(r"^[ \t]*\r?\n", "", tokens[i + 1])

    def _render_range(start: int, end: int, local_ctx: dict) -> str:
        out = []
        idx = start
        while idx < end:
            tok = tokens[idx]
            if tok.startswith("{{") and tok.endswith("}}"):
                expr = tok[2:-2].strip()
                out.append(_stdlib_eval_expr(expr, local_ctx))
                idx += 1
            elif tok.startswith("{%") and tok.endswith("%}"):
                tag = tok[2:-2].strip().lstrip("-").rstrip("-").strip()
                if tag.startswith("for ") and " in " in tag:
                    # Find matching endfor
                    depth = 1
                    end_idx = idx + 1
                    while end_idx < end and depth > 0:
                        t_inner = tokens[end_idx]
                        if t_inner.startswith("{%"):
                            inner_tag = t_inner[2:-2].strip().lstrip("-").rstrip("-").strip()
                            if inner_tag.startswith("for "):
                                depth += 1
                            elif inner_tag == "endfor":
                                depth -= 1
                        end_idx += 1
                    body_end = end_idx - 1
                    spec = tag[4:].strip()
                    var_part, iter_part = [x.strip() for x in spec.split(" in ", 1)]
                    iterable = _lookup_path(iter_part, local_ctx) or []
                    var_names = [v.strip() for v in var_part.split(",")]
                    for item in iterable:
                        loop_ctx = dict(local_ctx)
                        if len(var_names) == 2 and isinstance(item, (tuple, list)) and len(item) == 2:
                            loop_ctx[var_names[0]] = item[0]
                            loop_ctx[var_names[1]] = item[1]
                        else:
                            loop_ctx[var_names[0]] = item
                        out.append(_render_range(idx + 1, body_end, loop_ctx))
                    idx = end_idx
                elif tag.startswith("if "):
                    # Collect branches (if / elif / else) until matching endif
                    depth = 1
                    scan = idx + 1
                    branches = []
                    cur_cond = tag[3:].strip()
                    cur_start = idx + 1
                    while scan < end and depth > 0:
                        t_inner = tokens[scan]
                        if t_inner.startswith("{%"):
                            inner_tag = t_inner[2:-2].strip().lstrip("-").rstrip("-").strip()
                            if inner_tag.startswith("if "):
                                depth += 1
                            elif inner_tag == "endif":
                                depth -= 1
                                if depth == 0:
                                    branches.append((cur_cond, cur_start, scan))
                                    break
                            elif depth == 1 and inner_tag.startswith("elif "):
                                branches.append((cur_cond, cur_start, scan))
                                cur_cond = inner_tag[5:].strip()
                                cur_start = scan + 1
                            elif depth == 1 and inner_tag == "else":
                                branches.append((cur_cond, cur_start, scan))
                                cur_cond = "true"
                                cur_start = scan + 1
                        scan += 1
                    for b_cond, b_start, b_end in branches:
                        if _eval_condition(b_cond, local_ctx):
                            out.append(_render_range(b_start, b_end, local_ctx))
                            break
                    idx = scan + 1
                else:
                    idx += 1
            else:
                out.append(tok)
                idx += 1
        return "".join(out)

    rendered = _render_range(0, len(tokens), ctx)
    for r_idx, r_val in enumerate(raw_blocks):
        rendered = rendered.replace(f"__RAW_BLOCK_{r_idx}__", r_val)
    return rendered


def render_template(template_path, context):
    """
    渲染目標檔案：
    - 若目標為 hosts.yml.j2，統一委託 engine.classifier 產出多維度分類 Inventory [ARCH-01]。
    - 其餘模板一律由 100% Python 標準庫模板引擎 (_stdlib_render_j2) 渲染 [INV-01, CODE-05]。
    """
    t_path = Path(template_path)
    if t_path.name == "hosts.yml.j2":
        if str(OPS_DIR) not in sys.path:
            sys.path.insert(0, str(OPS_DIR))
        from engine.classifier import load_node_files, classify_nodes, render_hosts_yaml
        nodes = load_node_files(write_back=False)
        if nodes:
            return render_hosts_yaml(classify_nodes(nodes))

    with open(t_path, "r", encoding="utf-8") as f:
        template_str = f.read()
    return _stdlib_render_j2(template_str, context)


def build_compilation_targets(args, context, base_dir: Path, dest_prefix: str):
    """建構需要編譯渲染的目標矩陣清單"""
    c_val = context.get("cluster", "generic")
    cluster_name = (c_val.get("name", "generic") if isinstance(c_val, dict) else str(c_val)).lower()
    ssh_config_rel = "ssh-config/openlab/config" if cluster_name == "openlab" else "ssh-config/config"

    targets = [
        {
            "template": TEMPLATES_DIR / "ansible" / "hosts.yml.j2",
            "rel_dest": "inventory/hosts.yml",
            "repo_type": "ansible",
            "ops_internal_dest": OPS_DIR / "ansible" / "inventory" / "hosts.yml",
            "compare_file": base_dir / f"{dest_prefix}ansible" / "inventory" / "hosts.yml",
        },
        {
            "template": TEMPLATES_DIR / "ansible" / "group_vars_all.yml.j2",
            "rel_dest": "group_vars/all.yml",
            "repo_type": "ansible",
            "ops_internal_dest": OPS_DIR / "ansible" / "group_vars" / "all.yml",
            "compare_file": base_dir / f"{dest_prefix}ansible" / "group_vars" / "all.yml",
        },
        {
            "template": TEMPLATES_DIR / "configs" / "ssh_config.j2",
            "rel_dest": ssh_config_rel,
            "repo_type": "configs",
            "ops_internal_dest": None,
            "compare_file": base_dir / f"{dest_prefix}configs" / ssh_config_rel,
        },
        {
            "template": TEMPLATES_DIR / "configs" / "ssh_config.j2",
            "rel_dest": "ssh-config/config",
            "repo_type": "secrets",
            "ops_internal_dest": None,
            "compare_file": base_dir / f"{dest_prefix}secrets" / "ssh-config" / "config",
        },
        {
            "template": TEMPLATES_DIR / "configs" / "backup_profiles.yml.j2",
            "rel_dest": "conf/backup_profiles.yml",
            "repo_type": "configs",
            "ops_internal_dest": None,
            "compare_file": base_dir / f"{dest_prefix}configs" / "conf" / "backup_profiles.yml",
        },
    ]

    wf_template_dir = TEMPLATES_DIR / "workflows"
    if wf_template_dir.exists():
        for t_file in sorted(wf_template_dir.glob("*.yml.j2")):
            dest_filename = t_file.name[:-3]
            targets.append({
                "template": t_file,
                "rel_dest": f".gitea/workflows/{dest_filename}",
                "repo_type": "workflows",
                "ops_internal_dest": OPS_DIR / "workflows" / ".gitea" / "workflows" / dest_filename,
                "compare_file": base_dir / f"{dest_prefix}workflows" / ".gitea" / "workflows" / dest_filename,
            })

    return targets


def sync_directory_tree(
    src: Path,
    dst: Path,
    apply: bool,
    exclude_names=None,
    delete_stale: bool = False,
    transform_text_fn=None,
    rename_fn=None,
    allowlist_fn=None,
):
    """遞迴同步目錄樹，支援比對、相對路徑排除、檔名改寫與文字脫敏轉換"""
    if exclude_names is None:
        exclude_names = set()
    default_ignores = {"__pycache__", ".git", ".DS_Store"}

    total_synced = 0
    if not src.exists():
        return total_synced

    def is_excluded(rel_str: str, base_name: str) -> bool:
        if base_name in default_ignores or base_name in exclude_names:
            return True
        if rel_str in exclude_names:
            return True
        for ex in exclude_names:
            if ex.endswith("/") and rel_str.startswith(ex):
                return True
            if "/" in ex and (rel_str == ex or rel_str.startswith(ex + "/")):
                return True
        return False

    for root, dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src)
        dirs[:] = [
            d for d in dirs
            if not is_excluded(str((rel_root / d).as_posix()) if rel_root != Path(".") else d, d)
        ]

        for f in files:
            rel_file = rel_root / f if rel_root != Path(".") else Path(f)
            rel_file_str = str(rel_file.as_posix())
            if is_excluded(rel_file_str, f):
                continue
            if allowlist_fn and not allowlist_fn(rel_file_str):
                continue
            if any(f.endswith(ext) for ext in [".pyc", ".pyo", ".tmp"]):
                continue

            src_file = Path(root) / f
            dest_name = f
            if rename_fn:
                dest_name = rename_fn(rel_file_str, f)
                if dest_name is None:
                    continue

            target_file_rel = rel_root / dest_name if rel_root != Path(".") else Path(dest_name)
            dst_file = dst / target_file_rel

            new_bytes = None
            if transform_text_fn:
                ext = src_file.suffix.lower()
                binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".pyc", ".bin"}
                if ext not in binary_exts:
                    try:
                        text = src_file.read_text(encoding="utf-8")
                        transformed = transform_text_fn(text, str(target_file_rel.as_posix()))
                        new_bytes = transformed.encode("utf-8")
                    except UnicodeDecodeError:
                        new_bytes = src_file.read_bytes()
                else:
                    new_bytes = src_file.read_bytes()
            else:
                new_bytes = src_file.read_bytes()

            is_diff = True
            if dst_file.exists():
                try:
                    if dst_file.read_bytes() == new_bytes:
                        is_diff = False
                except Exception:
                    is_diff = True

            if is_diff:
                total_synced += 1
                if apply:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    dst_file.write_bytes(new_bytes)
                    try:
                        if os.access(src_file, os.X_OK):
                            dst_file.chmod(src_file.stat().st_mode)
                    except Exception:
                        pass
                    print(f"      \033[32m[COPIED]\033[0m {target_file_rel}")
                else:
                    print(f"      \033[33m[DIFF/NEW]\033[0m {target_file_rel}")

    if apply and delete_stale and dst.exists():
        for root, dirs, files in os.walk(dst, topdown=False):
            rel_path = Path(root).relative_to(dst)
            src_dir = src / rel_path
            for f in files:
                rel_f_str = str((rel_path / f).as_posix()) if rel_path != Path(".") else f
                if (allowlist_fn and not allowlist_fn(rel_f_str)) or is_excluded(rel_f_str, f) or any(f.endswith(ext) for ext in [".pyc", ".pyo"]):
                    (Path(root) / f).unlink(missing_ok=True)
                    print(f"      \033[31m[REMOVED EXCLUDED/NON-WHITELIST]\033[0m {rel_f_str}")
                    continue
            if not src_dir.exists() and not os.listdir(root):
                try:
                    os.rmdir(root)
                except Exception:
                    pass

    return total_synced


def execute_full_federation_sync(args, context, base_dir: Path, dest_prefix: str, site_name: str):
    """執行全庫聯邦代碼與站點疊加層同步至下游 5 大倉庫 (homelab-*)"""
    print("\n" + "=" * 68)
    print("  Federation Code & Site Overlay Synchronization")
    print(f"  Target Base: {base_dir}")
    print(f"  Repo Prefix: {dest_prefix}")
    print(f"  Site Overlay: {site_name}")
    print("=" * 68)

    operations_dir = base_dir / f"{dest_prefix}operations"
    configs_dir = base_dir / f"{dest_prefix}configs"
    secrets_dir = base_dir / f"{dest_prefix}secrets"

    # Legacy separate dirs fallback for non-destructive evolution [INV-08]
    legacy_ansible_dir = base_dir / f"{dest_prefix}ansible"
    legacy_tools_dir = base_dir / f"{dest_prefix}tools"
    legacy_workflows_dir = base_dir / f"{dest_prefix}workflows"

    has_unified_dest = operations_dir.exists()
    has_legacy_dest = any(d.exists() for d in [legacy_ansible_dir, legacy_tools_dir, legacy_workflows_dir])

    if not (has_unified_dest or has_legacy_dest or configs_dir.exists() or secrets_dir.exists()) and not getattr(args, "create_dest_dirs", False):
        print("  [•] Downstream repos do not exist locally on disk (Federation hosted on Gitea). Skipping local directory sync.")
        return

    # 1. 同步 Unified Operations Repo (${dest_prefix}operations) 或 Legacy 分離庫
    if has_unified_dest or getattr(args, "create_dest_dirs", False) or not has_legacy_dest:
        print(f"\n[*] Synchronizing Unified Operations Hub ({operations_dir.name})...")
        sync_directory_tree(OPS_DIR / "ansible", operations_dir / "ansible", args.apply)
        sync_directory_tree(OPS_DIR / "tools", operations_dir / "tools", args.apply)
        sync_directory_tree(OPS_DIR / "workflows", operations_dir / "workflows", args.apply)
        sync_directory_tree(OPS_DIR / "bin", operations_dir / "bin", args.apply)
    else:
        print("\n[*] Synchronizing Legacy Separated Repositories (Ansible, Tools, Workflows)...")
        sync_directory_tree(OPS_DIR / "ansible" / "roles", legacy_ansible_dir / "roles", args.apply)
        sync_directory_tree(OPS_DIR / "ansible" / "playbooks", legacy_ansible_dir / "playbooks", args.apply)
        sync_directory_tree(OPS_DIR / "ansible" / "scripts", legacy_ansible_dir / "scripts", args.apply)
        sync_directory_tree(OPS_DIR / "tools" / "bin", legacy_tools_dir / "bin", args.apply)
        sync_directory_tree(OPS_DIR / "tools" / "lib", legacy_tools_dir / "lib", args.apply)
        if (OPS_DIR / "tools" / "conf").exists():
            sync_directory_tree(OPS_DIR / "tools" / "conf", legacy_tools_dir / "conf", args.apply)
        sync_directory_tree(OPS_DIR / "workflows" / ".gitea" / "actions", legacy_workflows_dir / ".gitea" / "actions", args.apply)

    # 4. 同步 CMDB 地面事實 (node-information) 與不可變規格 (schema)
    if configs_dir.exists() or getattr(args, "create_dest_dirs", False):
        configs_dir.mkdir(parents=True, exist_ok=True)
        print("\n[*] Synchronizing Sensory Ground Truth (node-information)...")
        node_info_dir = configs_dir / "node-information"
        if args.apply:
            node_info_dir.mkdir(parents=True, exist_ok=True)

        if getattr(args, "legacy_sync", False) and (base_dir / "homelab-configs").exists() and (base_dir / "homelab-configs").resolve() != configs_dir.resolve():
            for sub in ["node-information", "network", "shell", "editor"]:
                if (base_dir / "homelab-configs" / sub).exists():
                    sync_directory_tree(base_dir / "homelab-configs" / sub, configs_dir / sub, args.apply)
        else:
            # 從探測收集到的 conf/nodes/*.json 產生全新的 node-information/node_<hostname>.json
            nodes_src_dir = OPS_DIR / "conf" / "nodes"
            if nodes_src_dir.exists():
                for nf in sorted(nodes_src_dir.glob("*.json")):
                    if nf.name in ("current.json", "archive") or nf.name.startswith("."):
                        continue
                    hname = nf.stem[5:] if nf.stem.startswith("node_") else nf.stem
                    dest_file = node_info_dir / f"node_{hname}.json"
                    if args.apply:
                        shutil.copy2(nf, dest_file)
                        print(f"      \033[32m[GENERATED FACT]\033[0m node_{hname}.json")
                    else:
                        print(f"      \033[33m[NEW FACT]\033[0m node_{hname}.json")

            # 同步不可變規格 (schema)
            if (OPS_DIR / "schema").exists():
                sync_directory_tree(OPS_DIR / "schema", configs_dir / "schema", args.apply)

    # 5. 同步金鑰輪換公鑰與端點 SSH 組態 (secrets)
    secrets_dir = base_dir / f"{dest_prefix}secrets"
    if secrets_dir.exists() or getattr(args, "create_dest_dirs", False):
        secrets_dir.mkdir(parents=True, exist_ok=True)
        print("\n[*] Synchronizing Secrets Structure & Public Keys...")
        if getattr(args, "legacy_sync", False) and (base_dir / "homelab-secrets").exists() and (base_dir / "homelab-secrets").resolve() != secrets_dir.resolve():
            for sub in ["ssh-config", "ssh-key", "docs"]:
                if (base_dir / "homelab-secrets" / sub).exists():
                    sync_directory_tree(base_dir / "homelab-secrets" / sub, secrets_dir / sub, args.apply)
            if (base_dir / "homelab-secrets" / "README.md").exists() and args.apply:
                shutil.copy2(base_dir / "homelab-secrets" / "README.md", secrets_dir / "README.md")
        else:
            # 零依賴從本機 ~/.ssh/ 收集全新公鑰 (*.pub) - 遵循 INV-02 嚴禁私鑰入庫
            ssh_key_dir = secrets_dir / "ssh-key"
            if args.apply:
                ssh_key_dir.mkdir(parents=True, exist_ok=True)
            ssh_dir = Path.home() / ".ssh"
            if ssh_dir.exists():
                for pub in sorted(ssh_dir.glob("*.pub")):
                    dest_pub = ssh_key_dir / pub.name
                    if args.apply:
                        shutil.copy2(pub, dest_pub)
                        print(f"      \033[32m[COPIED PUBKEY]\033[0m {pub.name}")
                    else:
                        print(f"      \033[33m[NEW PUBKEY]\033[0m {pub.name}")

            # 確保安全手冊結構存在
            if (OPS_DIR / "docs" / "security").exists():
                sync_directory_tree(OPS_DIR / "docs" / "security", secrets_dir / "docs" / "security", args.apply)
            if not (secrets_dir / "README.md").exists() and args.apply:
                (secrets_dir / "README.md").write_text("# Secrets Repository\n\nZero-Trust SSH public keys and endpoint access configurations.\n", encoding="utf-8")


def compare_federation_trees(base_dir: Path, prefix1: str, prefix2: str):
    """
    全量比對兩大聯邦倉庫群 (如 openlab-* vs homelab-*) 之結構與實質差異
    """
    print("\n" + "=" * 68)
    print(f"  Federation Comparison Matrix: {prefix1}* vs {prefix2}*")
    print(f"  Base Directory: {base_dir}")
    print("=" * 68)

    repo_archetypes = ["operations", "configs", "secrets"]
    # If legacy split directories exist, also compare them
    for legacy_arch in ["ansible", "tools", "workflows"]:
        if (base_dir / f"{prefix1}{legacy_arch}").exists() or (base_dir / f"{prefix2}{legacy_arch}").exists():
            if legacy_arch not in repo_archetypes:
                repo_archetypes.append(legacy_arch)
    total_identical = 0
    total_diff = 0
    total_new = 0
    total_missing = 0

    for arch in repo_archetypes:
        dir1 = base_dir / f"{prefix1}{arch}"
        dir2 = base_dir / f"{prefix2}{arch}"

        print(f"\n[*] Comparing Component: {arch.upper()} ({dir1.name} <-> {dir2.name})")
        if not dir1.exists() or not dir2.exists():
            print(f"    [!] Directory existence check: {dir1.name}={dir1.exists()} vs {dir2.name}={dir2.exists()}")
            continue

        files1 = {}
        for root, dirs, files in os.walk(dir1):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".DS_Store"}]
            for f in files:
                if f.endswith((".pyc", ".tmp")):
                    continue
                p = Path(root) / f
                files1[p.relative_to(dir1)] = p

        files2 = {}
        for root, dirs, files in os.walk(dir2):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".DS_Store"}]
            for f in files:
                if f.endswith((".pyc", ".tmp")):
                    continue
                p = Path(root) / f
                files2[p.relative_to(dir2)] = p

        all_rel = sorted(set(files1.keys()) | set(files2.keys()))
        repo_diff_count = 0

        for rel in all_rel:
            f1 = files1.get(rel)
            f2 = files2.get(rel)

            if f1 and not f2:
                print(f"    \033[36m[NEW in {prefix1}]\033[0m {rel}")
                total_new += 1
                repo_diff_count += 1
            elif f2 and not f1:
                print(f"    \033[33m[ONLY in {prefix2}]\033[0m {rel}")
                total_missing += 1
                repo_diff_count += 1
            else:
                try:
                    b1 = f1.read_bytes()
                    b2 = f2.read_bytes()
                    if b1 == b2:
                        total_identical += 1
                    else:
                        print(f"    \033[35m[MODIFIED]\033[0m {rel}")
                        total_diff += 1
                        repo_diff_count += 1
                except Exception as e:
                    print(f"    \033[31m[ERROR]\033[0m {rel}: {e}")

        if repo_diff_count == 0:
            print(f"    \033[32m[✓ 100% PARITY]\033[0m All tracked files are completely identical!")

    print("\n" + "=" * 68)
    print(f"  Summary: {total_identical} Identical | {total_diff} Modified | {total_new} New in {prefix1} | {total_missing} Only in {prefix2}")
    print("=" * 68)


def tools_lib_rename(rel_path: str, basename: str) -> str:
    if basename.startswith("labadmin_"):
        return "lab_" + basename[5:]
    return basename


def docs_rename(rel_path: str, basename: str) -> str:
    if basename.startswith("labadmin-"):
        return "lab-" + basename[5:]
    return basename


OPENLAB_ALLOWED_DOCS = {
    # 根手冊
    "README.md",
    # Ansible 通用手冊
    "ansible/README.md",
    "ansible/custom-package-facts.md",
    "ansible/inventory.md",
    "ansible/roles-modularization-spec.md",
    "ansible/playbooks/dotfiles-deployment.md",
    "ansible/playbooks/endpoint-bootstrap.md",
    "ansible/playbooks/node-provisioning.md",
    "ansible/playbooks/package-management.md",
    "ansible/playbooks/playbooks-overview.md",
    "ansible/scripts/audit-nodes.md",
    "ansible/scripts/sync-host-package-vars.md",
    # 架構核心規格
    "architecture/ansible-architecture.md",
    "architecture/code-config-separation-plan.md",
    "architecture/dagger-testing-environment-spec.md",
    "architecture/federation-synthesis-spec.md",
    "architecture/incubator-and-initialization-spec.md",
    "architecture/node-onboarding-and-ingestion-spec.md",
    "architecture/package-information-spec.md",
    "architecture/playbook-parameterized-abstraction-spec.md",
    "architecture/template-compiler-and-neutral-roles.md",
    "architecture/tools-architecture.md",
    "architecture/tools-workflow-playbook-mapping.md",
    # 安全通用規格
    "security/action-secrets-spec.md",
    "security/ssh-key-mapping.md",
    "security/ssh-keys-spec.md",
    # 工具庫手冊
    "tools/README.md",
    "tools/curses-tui-spec.md",
    "tools/endpoint-ssh-tools.md",
    "tools/installation-spec.md",
    "tools/labadmin-backup.md",
    "tools/labadmin-info.md",
    "tools/labadmin-node.md",
    "tools/labadmin-setup.md",
    "tools/labadmin-ssh.md",
    "tools/labadmin-status.md",
    "tools/labadmin-tools.md",
    "tools/labadmin-upgrade.md",
    "tools/ssh-tools-integration.md",
    "tools/todo.md",
    "tools/versioning-spec.md",
    "tools/core/config.md",
    "tools/core/gitea-api.md",
    "tools/core/live-probe.md",
    "tools/core/render-node-doc.md",
    "tools/core/ui-menu.md",
    "tools/core/ui-theme.md",
    "tools/core/version.md",
    # 使用者操作手冊
    "user_manual/README.md",
    # Workflows 通用指南
    "workflows/README.md",
    "workflows/post-push-trigger.md",
    "workflows/sync-package-inventory.md",
    "workflows/workflows-guide.md",
}


def is_openlab_doc_allowed(rel_doc_path: str) -> bool:
    """依據 docs/architecture/openlab-distill-sanitization-spec.md §3 判定手冊是否在白名單內"""
    if rel_doc_path.startswith("user_manual/"):
        return True
    norm_path = rel_doc_path.replace("tools/lab-", "tools/labadmin-")
    return rel_doc_path in OPENLAB_ALLOWED_DOCS or norm_path in OPENLAB_ALLOWED_DOCS


# Downstream OpenLabOps stub
def sanitize_openlab_text(content: str, rel_path: str = '') -> str:
    return content

def verify_openlabops_sanitization(target_dir: Path):
    return True

def distill_openlabops_hub(args):
    print('  [INFO] OpenLabOps is the distilled downstream operations hub.')
    return 0

def _execute_distill_openlabops_hub(args):
    return 0

def _get_engine_version() -> str:
    ver_file = OPS_DIR / "VERSION"
    if ver_file.exists():
        return ver_file.read_text(encoding="utf-8").strip() or "1.0.0"
    return "1.0.0"


def main():
    prog_name = "labadmin-diff" if ("--diff" in sys.argv and "--apply" not in sys.argv) else "labadmin-apply"
    parser = argparse.ArgumentParser(prog=prog_name, description="OpenLabOps / OpenLabOps Manifest Compiler & Repository Engine")
    parser.add_argument("-v", "--version", action="version", version=f"OpenLabOps Manifest Compiler ({prog_name}) v{_get_engine_version()}")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest file path (default: conf/openlab.manifest.yml)")
    parser.add_argument("--site", default=None, help="Site overlay name (default: auto-detected from manifest cluster name)")
    parser.add_argument("--diff", action="store_true", help="Compare against current downstream repos")
    parser.add_argument("--apply", action="store_true", help="Write rendered files and sync federation to destination directories")
    parser.add_argument("--dest-prefix", default=None, help="Target downstream repo prefix (default: from manifest repo_prefix or homelab-)")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Target base directory (default: parent of operations directory)")
    parser.add_argument("--ops-internal", action="store_true", help="Also apply rendered files to openlabops internal paths")
    parser.add_argument("--create-dest-dirs", action="store_true", help="Create downstream repo directories in base-dir if they do not exist")
    parser.add_argument("--full-federation", action="store_true", help="Synthesize and sync all non-template federation core code to homelab-*")
    parser.add_argument("--legacy-sync", action="store_true", help="Synchronize legacy homelab-configs/homelab-secrets instead of newly discovered telemetry")
    args = parser.parse_args()

    if args.apply:
        lib_dir = str(OPS_DIR / "tools" / "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from core.lockout import enforce_lockout_guard
        enforce_lockout_guard("labadmin-apply")



    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Error: Manifest file {manifest_path} not found.")
        sys.exit(1)

    context = parse_simple_yaml(manifest_path)
    if CORE_MANIFEST.exists():
        core_ctx = parse_simple_yaml(CORE_MANIFEST)
        context["_core"] = core_ctx

    if "inventory" not in context or not isinstance(context["inventory"], dict):
        context["inventory"] = {}

    c_val = context.get("cluster")
    c_name = c_val.get("name", "") if isinstance(c_val, dict) else str(c_val or "")
    m_name = manifest_path.name.lower()
    is_openlab = (
        "openlab" in m_name
        or "openlab" in c_name.lower()
        or context.get("default_target_user") == "ansible"
        or (isinstance(c_val, dict) and c_val.get("ansible_user") == "ansible")
        or "openlab" in OPS_DIR.name.lower()
    )

    cur_lang = os.getenv("LAB_LANG") or os.getenv("LAB_LANG")
    def_locale = f"{cur_lang}.UTF-8" if cur_lang else "en_US.UTF-8"
    def_tz = "UTC"

    if "cluster" not in context or not isinstance(context["cluster"], dict):
        c_name = str(context.get("cluster") or ("OpenLab-Mock" if is_openlab else "Cluster-Mock"))
        context["cluster"] = {
            "name": c_name,
            "domain": "lab" if is_openlab else "local",
            "admin_user": os.getenv("USER", "labadmin" if is_openlab else "admin"),
            "ansible_user": context.get("default_target_user", "ansible"),
            "timezone": def_tz,
            "locale": def_locale
        }
    else:
        context["cluster"].setdefault("name", "OpenLab" if is_openlab else "Cluster")
        context["cluster"].setdefault("domain", "lab" if is_openlab else "local")
        context["cluster"].setdefault("admin_user", os.getenv("USER", "labadmin" if is_openlab else "admin"))
        context["cluster"].setdefault("ansible_user", context.get("default_target_user", "ansible"))
        context["cluster"].setdefault("timezone", def_tz)
        context["cluster"].setdefault("locale", def_locale)

    ansible_u = context["cluster"].get("ansible_user", "ansible")
    if "keys" not in context or not isinstance(context["keys"], dict):
        context["keys"] = {
            "ansible": f"{ansible_u}.key",
            "user": "id_user.key",
            "git": "git.key"
        }

    if "networks" not in context or not isinstance(context["networks"], dict):
        cidr = context.get("network_cidr", "192.168.1.0/24")
        context["networks"] = {
            "service_lan": cidr,
            "flat_lan": cidr,
            "wg_lan": cidr,
            "user_lan": cidr
        }
    else:
        context["networks"].setdefault("service_lan", "192.168.1.0/24")

    if "git_platform" not in context or not isinstance(context["git_platform"], dict):
        context["git_platform"] = {
            "host": "gitea.lab" if is_openlab else "gitea.local",
            "ip": "192.168.1.90",
            "ssh_port": 22,
            "http_port": 3000 if is_openlab else 80,
            "org": "OpenLabOps" if is_openlab else "ClusterOps",
            "repo_prefix": "openlab" if is_openlab else "cluster"
        }

    inv_groups, inv_nodes = extract_inventory_metadata(context, OPS_DIR)
    context["inventory_groups"] = inv_groups
    context["inventory_nodes"] = inv_nodes
    try:
        if str(OPS_DIR) not in sys.path:
            sys.path.insert(0, str(OPS_DIR))
        from engine.classifier import load_node_files
        context["nodes"] = load_node_files(write_back=False)
    except Exception:
        context["nodes"] = []

    cluster_val = context.get("cluster", "Generic")
    if isinstance(cluster_val, dict):
        cluster_name = cluster_val.get("name", "Generic")
    else:
        cluster_name = str(cluster_val) if cluster_val else "Generic"
    site_name = args.site if args.site else cluster_name.lower()
    base_dir = Path(args.base_dir)

    dest_prefix = args.dest_prefix
    if not dest_prefix:
        repo_prefix = context.get("git_platform", {}).get("repo_prefix")
        if not repo_prefix:
            repo_prefix = "openlab"
        dest_prefix = f"{repo_prefix}-" if not repo_prefix.endswith("-") else repo_prefix

    print("=" * 68)
    print("  OpenLabOps / OpenLabOps Compiler Engine (Template Rendering)")
    print(f"  Manifest    : {manifest_path}")
    print(f"  Cluster     : {cluster_name}")
    print(f"  Base Dir    : {base_dir}")
    print(f"  Repo Prefix : {dest_prefix}")
    print(f"  Site Name   : {site_name}")
    print(f"  Full Sync   : {args.full_federation}")
    print("=" * 68)

    targets = build_compilation_targets(args, context, base_dir, dest_prefix)
    total_rendered = 0
    total_written = 0

    for t in targets:
        total_rendered += 1
        rendered = render_template(t["template"], context).strip() + "\n"
        out_repo_dir = base_dir / f"{dest_prefix}{t['repo_type']}"
        dest_file = out_repo_dir / t["rel_dest"]

        print(f"\n[+] Target: {dest_file.name} ({t['repo_type']}: {t['rel_dest']})")

        comp = t.get("compare_file")
        if (not comp or not comp.exists()) and t.get("ops_internal_dest"):
            comp = t.get("ops_internal_dest")
        if comp and comp.exists():
            existing = comp.read_text(encoding="utf-8")
            diff = list(difflib.unified_diff(
                existing.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile=f"baseline: {comp.name}",
                tofile=f"rendered: {dest_file.name}",
                n=2
            ))
            if not diff:
                print(f"    \033[32m[100% IDENTICAL]\033[0m Matches current {comp.parent.name}/{comp.name}")
            else:
                print(f"    \033[33m[DIFF DETECTED]\033[0m Differences from current baseline:")
                for line in diff[:10]:
                    if line.startswith("+"):
                        sys.stdout.write(f"      \033[32m{line}\033[0m")
                    elif line.startswith("-"):
                        sys.stdout.write(f"      \033[31m{line}\033[0m")
                    else:
                        sys.stdout.write(f"      {line}")
                if len(diff) > 10:
                    print(f"      ... ({len(diff) - 10} more diff lines)")
        else:
            print(f"    \033[36m[NEW / RENDERED]\033[0m Template ready for output")

        if args.apply:
            if out_repo_dir.exists() or getattr(args, "create_dest_dirs", False):
                out_repo_dir.mkdir(parents=True, exist_ok=True)
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(rendered, encoding="utf-8")
                print(f"    \033[32m[WRITTEN]\033[0m -> {dest_file}")
                total_written += 1
            else:
                print(f"    \033[33m[SKIPPED LOCAL]\033[0m Local repo {out_repo_dir.name} not checked out (Downstream managed via Gitea)")

            if args.ops_internal and t.get("ops_internal_dest"):
                ops_dest = t["ops_internal_dest"]
                ops_dest.parent.mkdir(parents=True, exist_ok=True)
                ops_dest.write_text(rendered, encoding="utf-8")
                print(f"    \033[32m[OPS INTERNAL]\033[0m -> {ops_dest}")

    if args.full_federation:
        execute_full_federation_sync(args, context, base_dir, dest_prefix, site_name)

    print("\n" + "=" * 68)
    print(f"Compilation Summary: {total_rendered} templates processed.")
    if not args.apply:
        print("[!] Dry-run complete. Run with --apply to compile output into repositories.")
    else:
        print(f"[✓] Output applied successfully: {total_written} template files written.")


if __name__ == "__main__":
    main()
