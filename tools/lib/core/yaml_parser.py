#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenLabOps Shared Pure-Python YAML Parser & Inventory Extractor
100% Python 3 Standard Library [INV-01].
Provides a single source of truth for parsing declarative manifests,
eliminating duplicate ad-hoc line/indentation parsers across engine/ and tools/.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Union


def parse_scalar(val_str: str) -> Any:
    """將 YAML 純量或行內列表字串轉換為對應之 Python 型別"""
    s = val_str.strip()
    if not s:
        return ""
    if not ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
        if " #" in s:
            s = s.split(" #", 1)[0].strip()
        elif "\t#" in s:
            s = s.split("\t#", 1)[0].strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        try:
            return json.loads(s.replace("'", '"'))
        except Exception:
            inner = s[1:-1].strip()
            return [x.strip().strip('"\'') for x in inner.split(",") if x.strip()] if inner else []
    if s.startswith("{") and s.endswith("}"):
        try:
            return json.loads(s.replace("'", '"'))
        except Exception:
            return {}
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none", "~"):
        return None
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    return s


def parse_yaml_text(text: str) -> Dict[str, Any]:
    """解析 YAML 字串為巢狀 dict / list 結構（支援 dict 內嵌 list 與 list of dicts）"""
    raw_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        raw_lines.append((indent, stripped))

    root: Dict[str, Any] = {}
    stack: List[tuple] = [(-1, root)]

    for idx, (indent, stripped) in enumerate(raw_lines):
        is_list_item = stripped.startswith("- ")
        while len(stack) > 1:
            top_indent, top_container = stack[-1]
            # 若當前為列表項目且棧頂即為該列表 (允許與父鍵同縮排或大於父鍵縮排)
            if is_list_item and isinstance(top_container, list) and indent >= top_indent:
                break
            if indent <= top_indent:
                stack.pop()
            else:
                break

        parent = stack[-1][1]

        if is_list_item:
            item_content = stripped[2:].strip()
            if not isinstance(parent, list):
                continue
            if (": " in item_content or item_content.endswith(":")) and not (item_content.startswith('"') or item_content.startswith("'")):
                k, v = item_content.split(":", 1)
                k = k.strip().strip('"\'')
                v_str = v.strip()
                new_dict: Dict[str, Any] = {}
                if v_str and not v_str.startswith("#"):
                    new_dict[k] = parse_scalar(v_str)
                else:
                    new_dict[k] = {}
                parent.append(new_dict)
                stack.append((indent, new_dict))
            else:
                parent.append(parse_scalar(item_content))
        elif ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip().strip('"\'')
            v_str = v.strip()
            if v_str and not v_str.startswith("#"):
                if isinstance(parent, dict):
                    parent[k] = parse_scalar(v_str)
            else:
                next_is_list = False
                if idx + 1 < len(raw_lines):
                    next_indent, next_stripped = raw_lines[idx + 1]
                    if next_indent >= indent and next_stripped.startswith("- "):
                        next_is_list = True
                container: Union[List[Any], Dict[str, Any]] = [] if next_is_list else {}
                if isinstance(parent, dict):
                    parent[k] = container
                    stack.append((indent, container))

    return root


def parse_yaml_file(filepath: Union[str, Path]) -> Dict[str, Any]:
    """讀取並解析 YAML 檔案"""
    p = Path(filepath)
    if not p.exists():
        return {}
    return parse_yaml_text(p.read_text(encoding="utf-8"))


def extract_manifest_hosts_metadata(manifest_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    從已解析之 Manifest dict 遞迴提取 inventory 下所有主機之完整元數據：
    回傳 {hostname: {"ip": ..., "category": ..., "subgroup": ..., "roles": [...], "user": ..., "key_name": ..., "key_profile": ...}}
    """
    inv = manifest_data.get("inventory", {})
    if not isinstance(inv, dict):
        return {}

    meta_map: Dict[str, Dict[str, Any]] = {}

    def _walk(node: Any, top_cat: str = "server", subgroup: str = "", inherited: Dict[str, Any] = None):
        if not isinstance(node, dict):
            return
        inherited = dict(inherited or {})
        for attr in ("key_profile", "key_name", "ansible_user", "user"):
            if attr in node and not isinstance(node[attr], dict):
                inherited[attr] = node[attr]

        if "hosts" in node and isinstance(node["hosts"], dict):
            for hname, hdata in node["hosts"].items():
                if not isinstance(hdata, dict):
                    continue
                ip = str(hdata.get("ansible_host", "")).strip()
                if not ip:
                    continue
                roles = hdata.get("roles", [])
                if not isinstance(roles, list):
                    roles = [str(roles)] if roles else []
                meta_map[hname] = {
                    "ip": ip,
                    "category": top_cat,
                    "subgroup": subgroup,
                    "roles": roles,
                    "hostname_fqdn": hdata.get("hostname", f"{hname}.lab"),
                    "user": hdata.get("user") or hdata.get("ansible_user") or inherited.get("ansible_user") or inherited.get("user"),
                    "key_name": hdata.get("key_name") or inherited.get("key_name"),
                    "key_profile": hdata.get("key_profile") or inherited.get("key_profile"),
                }

        for k, v in node.items():
            if k == "hosts" or not isinstance(v, dict):
                continue
            next_cat = top_cat
            next_sub = subgroup
            if k == "dev":
                next_cat = "dev"
            elif k == "servers":
                next_cat = "server"
            elif k == "appliances":
                next_cat = "appliance"
            elif k in ("desktops", "endpoints"):
                next_cat = "desktop"
            else:
                next_sub = k
            _walk(v, next_cat, next_sub, inherited)

    _walk(inv)
    return meta_map

