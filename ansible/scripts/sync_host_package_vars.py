#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script: sync_host_package_vars.py
Description:
  Compares live package list from a node against Ansible host_vars (IaC)
  and synchronizes host_vars/<hostname>.yml and node-information/packages_<hostname>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

IAC_HEADER_MARKER = "# IaC Package Specification (Managed by sync-package-inventory.yml)"


def load_repo_packages(host_vars_file: str) -> tuple[list[str], list[str]]:
    """從 host_vars 檔案中以純 Python 標準庫解析 installed_packages 與 aur_packages 清單 [INV-01]。"""
    if not os.path.exists(host_vars_file):
        return [], []
    installed: list[str] = []
    aur: list[str] = []
    current_section = None
    try:
        with open(host_vars_file, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped.startswith('installed_packages:'):
                    current_section = 'installed'
                    continue
                elif stripped.startswith('aur_packages:'):
                    current_section = 'aur'
                    continue
                elif not line.startswith(' ') and not line.startswith('\t') and ':' in stripped:
                    current_section = None
                    continue

                if current_section and stripped.startswith('- '):
                    pkg = stripped[2:].split('#', 1)[0].strip().strip('"\'')
                    if pkg:
                        if current_section == 'installed':
                            installed.append(pkg)
                        elif current_section == 'aur':
                            aur.append(pkg)
        return installed, aur
    except Exception as e:
        sys.stderr.write(f"Error loading {host_vars_file}: {e}\n")
        return [], []


def compute_diff(live_packages: list[dict], repo_installed: list[str], repo_aur: list[str]) -> dict:
    """Computes added and removed packages between live node and repo IaC."""
    live_official = []
    live_aur = []

    for pkg in live_packages:
        name = pkg.get('name')
        if not name:
            continue
        if pkg.get('source') == 'yay' or pkg.get('repo') == 'aur':
            live_aur.append(name)
        else:
            live_official.append(name)

    live_official = sorted(set(live_official))
    live_aur = sorted(set(live_aur))
    live_all = sorted(set(live_official + live_aur))

    repo_installed_set = set(repo_installed)
    repo_aur_set = set(repo_aur)
    repo_all = sorted(repo_installed_set | repo_aur_set)

    added = sorted(set(live_all) - set(repo_all))
    removed = sorted(set(repo_all) - set(live_all))

    return {
        'has_drift': bool(added or removed),
        'live_count': len(live_all),
        'repo_count': len(repo_all),
        'added': added,
        'removed': removed,
        'live_official': live_official,
        'live_aur': live_aur,
        'repo_installed': repo_installed,
        'repo_aur': repo_aur,
    }


def update_host_vars_file(host_vars_file: str, official_pkgs: list[str], aur_pkgs: list[str]):
    """Updates or appends installed_packages and aur_packages to host_vars file preserving base vars."""
    existing_lines = []
    if os.path.exists(host_vars_file):
        with open(host_vars_file, 'r', encoding='utf-8') as f:
            existing_lines = f.readlines()

    # Find where previous IaC specification or installed_packages begins
    cut_idx = len(existing_lines)
    for i, line in enumerate(existing_lines):
        if IAC_HEADER_MARKER in line or re.match(r'^(installed_packages|aur_packages):', line):
            cut_idx = i
            break

    # Retain lines before the marker
    base_content = "".join(existing_lines[:cut_idx]).rstrip()

    new_section = [
        "",
        IAC_HEADER_MARKER,
        "installed_packages:",
    ]
    for pkg in sorted(set(official_pkgs)):
        new_section.append(f"  - {pkg}")

    if aur_pkgs:
        new_section.append("")
        new_section.append("aur_packages:")
        for pkg in sorted(set(aur_pkgs)):
            new_section.append(f"  - {pkg}")

    final_content = (base_content + "\n" + "\n".join(new_section) + "\n").lstrip()
    if not final_content.startswith("---"):
        final_content = "---\n" + final_content

    with open(host_vars_file, 'w', encoding='utf-8') as f:
        f.write(final_content)


def main():
    parser = argparse.ArgumentParser(description="Sync package inventory between live node and repo IaC.")
    parser.add_argument('--host', required=True, help="Inventory hostname")
    parser.add_argument('--host-vars-dir', default=os.path.join(os.path.dirname(__file__), '../host_vars'))
    parser.add_argument('--configs-dir', default=os.path.expanduser('~/openlab-configs/node-information'))
    parser.add_argument('--live-json', help="Path to JSON file containing live explicit packages")
    parser.add_argument('--diff', action='store_true', help="Check diff and output JSON")
    parser.add_argument('--apply', action='store_true', help="Update host_vars and configs JSON")

    args = parser.parse_args()

    live_pkgs = []
    metadata = {}
    if args.live_json and os.path.exists(args.live_json):
        with open(args.live_json, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            if isinstance(raw_data, dict):
                live_pkgs = raw_data.get('packages') or raw_data.get('explicit_packages') or []
                metadata = raw_data
            elif isinstance(raw_data, list):
                live_pkgs = raw_data
    elif not sys.stdin.isatty():
        try:
            raw_data = json.load(sys.stdin)
            if isinstance(raw_data, dict):
                live_pkgs = raw_data.get('packages') or raw_data.get('explicit_packages') or []
                metadata = raw_data
            elif isinstance(raw_data, list):
                live_pkgs = raw_data
        except Exception:
            pass

    host_vars_file = os.path.join(args.host_vars_dir, f"{args.host}.yml")
    repo_installed, repo_aur = load_repo_packages(host_vars_file)

    diff = compute_diff(live_pkgs, repo_installed, repo_aur)

    if args.apply:
        update_host_vars_file(host_vars_file, diff['live_official'], diff['live_aur'])
        # Also ensure openlab-configs JSON exists and is updated
        if os.path.exists(args.configs_dir):
            target_json = os.path.join(args.configs_dir, f"packages_{args.host}.json")
            if live_pkgs and (not os.path.exists(target_json) or metadata):
                dump_data = {
                    'inventory_hostname': args.host,
                    'package_manager': metadata.get('package_manager') or metadata.get('package_manager_detected') or 'unknown',
                    'distribution': metadata.get('distribution', 'unknown'),
                    'os_family': metadata.get('os_family', 'unknown'),
                    'explicit_packages_count': len(live_pkgs),
                    'packages': live_pkgs,
                }
                with open(target_json, 'w', encoding='utf-8') as f:
                    json.dump(dump_data, f, indent=2, ensure_ascii=False)
                    f.write('\n')

    if args.diff or not args.apply:
        print(json.dumps(diff, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
