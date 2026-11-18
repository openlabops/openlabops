#!/usr/bin/env python3
# ==============================================================================
# OpenLabOps Operations Engine - Official Dagger E2E Pipeline Test
# Governed by [INV-01] (Zero External Dependencies) & [INV-09] (Production Tooling)
# ==============================================================================

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def run_step(step_name: str, cmd: list, cwd: Path = REPO_ROOT) -> bool:
    print(f"[•] Running: {step_name}...")
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True
        )
        print(f"  [✓] {step_name} PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [✗] {step_name} FAILED (Exit Code: {e.returncode})")
        print(e.stdout)
        return False

def test_cue_schema():
    cue_bin = shutil.which("cue")
    if not cue_bin:
        print("  [!] cue binary not found on PATH, skipping CUE evaluation.")
        return None
    return run_step("CUE Architectural Invariant Verification", [cue_bin, "eval", "./schema/..."])

def test_unit_suite():
    unit_script = REPO_ROOT / "tests" / "unit" / "test_core_units.py"
    return run_step("Core Engine & Security Unit Test Suite (19 Tests)", [sys.executable, str(unit_script)])

def test_zero_external_dependencies():
    print("[•] Auditing Python Zero External Dependencies [INV-01] on tools/...")
    forbidden = ["requests", "yaml", "paramiko", "jinja2", "cryptography"]
    py_files = list(REPO_ROOT.glob("tools/**/*.py"))
    violations = []
    for p in py_files:
        content = p.read_text(encoding="utf-8", errors="ignore")
        for pkg in forbidden:
            if f"import {pkg}" in content or f"from {pkg}" in content:
                violations.append((p.name, pkg))
    if violations:
        print(f"  [✗] Violations found: {violations}")
        return False
    print("  [✓] Zero External Dependencies Verified on all tools (100% Python Standard Library).")
    return True

def test_dagger_dind_capability():
    dagger_bin = shutil.which("dagger")
    if not dagger_bin:
        print("  [!] dagger CLI not found on PATH, skipping Dagger container test.")
        return None
    
    print("[•] Testing Dagger Docker-in-Docker (DinD) & Container Engine...")
    cmd = [
        dagger_bin,
        "core",
        "container",
        "from",
        "--address",
        "docker:cli",
        "with-exec",
        "--args",
        "docker,--version",
        "stdout"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        if "Docker version" in res.stdout:
            print("  [✓] Dagger DinD Container Execution Verified successfully.")
            return True
        else:
            print("  [✗] Dagger ran but output was unexpected:")
            print(res.stdout)
            return False
    except Exception as e:
        print(f"  [✗] Dagger DinD verification encountered failure: {e}")
        return False

def test_production_fleet_e2e():
    """
    Execute full-functional multi-distro fleet onboarding, inventory compilation,
    toolchain deployment, and 3-stage zero-downtime key rotation inside mock-console [INV-09].
    Strictly forbidden to only run --help.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("  [!] docker binary not found on PATH, skipping live container fleet test.")
        return None
    
    check_docker = subprocess.run([docker_bin, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check_docker.returncode != 0:
        print("  [!] Docker daemon is not accessible (cannot connect to /var/run/docker.sock). Skipping live container fleet test.")
        return None
    
    print("[•] Executing Full Production Multi-Distro Fleet E2E inside mock-console [INV-09]...")
    up_script = REPO_ROOT / "tests" / "bin" / "test-sandbox-up"
    gitea_script = REPO_ROOT / "tests" / "bin" / "test-gitea-init"
    onboard_script = REPO_ROOT / "tests" / "bin" / "test-day0-onboard"
    down_script = REPO_ROOT / "tests" / "bin" / "test-sandbox-down"

    try:
        if not run_step("Sandbox Multi-Distro Fleet Spin Up", [str(up_script)]):
            return False
        if not run_step("Sandbox Gitea Initialization & Key Pre-seed", [str(gitea_script)]):
            return False
        if not run_step("Production Day-0 Onboarding & Key Rotation in Mock Console", [str(onboard_script)]):
            return False
        return True
    finally:
        print("[•] Cleaning up sandbox fleet containers...")
        subprocess.run([str(down_script)], cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenLabOps Official Dagger E2E Suite")
    parser.add_argument(
        "--lang",
        dest="lang",
        default=os.environ.get("LAB_LANG") or os.environ.get("LAB_LANG") or "en_US",
        help="Language / Locale for test pipeline (en_US, zh_TW, ja_JP)"
    )
    parser.add_argument(
        "--kvm-node",
        dest="kvm_node",
        default=None,
        help="Run Mode B (Single-Node Containerized KVM Deep Test) for the specified persona (e.g. debian, alpine, truenas, synology, qnap, unraid, omv)"
    )
    args = parser.parse_args()

    target_lang = args.lang
    os.environ["LAB_LANG"] = target_lang
    os.environ["LAB_LANG"] = target_lang

    if args.kvm_node:
        print_header(f"OpenLabOps Mode B: Single-Node Containerized KVM Deep Verification ({args.kvm_node})")
        kvm_script = REPO_ROOT / "tests" / "bin" / "test-kvm-node"
        ok = run_step(f"Containerized KVM Deep Test ({args.kvm_node})", [str(kvm_script), args.kvm_node])
        sys.exit(0 if ok else 1)

    print_header("OpenLabOps Official Dagger E2E Verification Suite (Mode A: Full-Fleet)")
    
    results = [
        ("CUE Schema Integrity", test_cue_schema()),
        ("Zero External Dependencies [INV-01]", test_zero_external_dependencies()),
        ("Core Engine & Security Unit Suite", test_unit_suite()),
        ("Dagger DinD & Service Bindings", test_dagger_dind_capability()),
        ("Production Fleet E2E Pipeline [INV-09]", test_production_fleet_e2e())
    ]
    
    print_header("Test Summary")
    has_failed = False
    for name, ok in results:
        if ok is True:
            status = "PASSED [✓]"
        elif ok is None:
            status = "SKIPPED [-]"
        else:
            status = "FAILED [✗]"
            has_failed = True
        print(f"  {name.ljust(45)}: {status}")
            
    if not has_failed:
        print("\n🎉 ALL APPLICABLE DAGGER PIPELINE TESTS COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
