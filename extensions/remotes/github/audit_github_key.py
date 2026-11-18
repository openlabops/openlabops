#!/usr/bin/env python3
"""
GitHub SSH Key & Connectivity Audit Probe (EXT-JSON-V1 compliant)
Zero external dependencies: 100% Python standard library.
"""

import sys
import json
import os
import subprocess
from pathlib import Path

def audit_github(key_path: str = None) -> dict:
    home = Path.home()
    if not key_path:
        for candidate in ["git.key", "id_ed25519"]:
            p = home / ".ssh" / candidate
            if p.exists():
                key_path = str(p)
                break

    result = {
        "schema_version": "1.0.0",
        "extension_name": "github-remote-audit",
        "target": "github.com",
        "key_path": key_path,
        "status": "UNKNOWN",
        "authenticated_user": None,
        "message": ""
    }

    if not key_path or not os.path.exists(key_path):
        result["status"] = "KEY_NOT_FOUND"
        result["message"] = f"SSH key not found at {key_path}"
        return result

    # Test SSH handshake to github.com
    # GitHub returns rc 1 on successful greeting: "Hi username! You've successfully authenticated..."
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=5",
        "-i", key_path,
        "-T", "git@github.com"
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        output = (proc.stdout + proc.stderr).strip()
        if "successfully authenticated" in output:
            result["status"] = "HEALTHY"
            # Extract user
            # "Hi <username>! You've successfully authenticated..."
            if "Hi " in output:
                user = output.split("Hi ")[1].split("!")[0].strip()
                result["authenticated_user"] = user
            result["message"] = output
        elif "Permission denied" in output:
            result["status"] = "UNAUTHORIZED"
            result["message"] = "Permission denied (publickey). Key is not registered on GitHub."
        else:
            result["status"] = "UNREACHABLE"
            result["message"] = output
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        result["message"] = "Connection to github.com timed out."
    except Exception as e:
        result["status"] = "ERROR"
        result["message"] = str(e)

    return result

def main():
    key_arg = sys.argv[1] if len(sys.argv) > 1 else None
    res = audit_github(key_arg)
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

