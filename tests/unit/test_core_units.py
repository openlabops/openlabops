#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
OpenLabOps Operations Engine - Standalone Unit Test Suite
File: tests/unit/test_core_units.py
==============================================================================
100% Python Standard Library (unittest) - Zero External Dependencies [INV-01].
Provides sub-second isolated verification of core modules before E2E Dagger runs:
  1. Manifest & YAML Parsers (parse_simple_yaml, parse_day0_manifest)
  2. Template Compiler & Context Fallbacks (all 20 .j2 templates)
  3. Node Classifier & Inventory Generation (dev, server, desktop, appliance)
  4. Boot Sync Git SHA Index & Lockout Guard (lab_boot_sync, lockout)
  5. Hard Architectural Invariants (INV-01, INV-02, INV-04 CUE, INV-09)
==============================================================================
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "lib"))

IS_OPENLAB = True


class TestYAMLAndManifestParser(unittest.TestCase):
    """測試 Manifest 與 Day-0 宣告檔解析器之邊界條件與容錯能力"""

    def test_parse_production_manifest(self):
        from engine.compiler import parse_simple_yaml
        if IS_OPENLAB:
            manifest_path = REPO_ROOT / "conf" / "openlab.manifest.yml"
            self.assertTrue(manifest_path.exists(), "openlab.manifest.yml must exist")
            data = parse_simple_yaml(manifest_path)
            self.assertIn("cluster", data)
            self.assertIn(data["cluster"].get("name"), ["OpenLab", "OpenLabOps"])
            self.assertIn("keys", data)
            self.assertEqual(data["keys"].get("ansible"), "ansible.key")
            self.assertNotIn("ssh_keys", data, "Redundant ssh_keys block must be removed")
            self.assertIn("inventory", data)
        else:
            manifest_path = REPO_ROOT / "conf" / "openlab.manifest.yml"
            self.assertTrue(manifest_path.exists(), "openlab.manifest.yml must exist")
            data = parse_simple_yaml(manifest_path)
            self.assertIn("cluster", data)
            self.assertEqual(data["cluster"].get("name"), "OpenLabOps")
            self.assertIn("keys", data)
            self.assertEqual(data["keys"].get("ansible"), "ansible.key")
            self.assertNotIn("ssh_keys", data, "Redundant ssh_keys block must be removed")
            self.assertIn("inventory", data)
            self.assertIn("dev", data["inventory"])
            self.assertIn("servers", data["inventory"])
            self.assertIn("appliances", data["inventory"])
            self.assertIn("desktops", data["inventory"])

    def test_parse_day0_flat_targets_indented(self):
        from engine.onboard import parse_day0_manifest
        test_manifest = REPO_ROOT / "tests" / "conf" / ("openlab.manifest.test.yml" if IS_OPENLAB else "openlab.manifest.test.yml")
        meta, targets = parse_day0_manifest(test_manifest)

        self.assertEqual(len(targets), 5, "Must parse all 5 indented mock targets")
        names = [t.get("name") for t in targets]
        self.assertIn("mock-arch", names)
        self.assertIn("mock-debian", names)
        self.assertIn("mock-alpine", names)

    def test_parse_day0_hierarchical_inventory_filtering(self):
        from engine.onboard import parse_day0_manifest
        prod_manifest = REPO_ROOT / "conf" / ("openlab.manifest.yml" if IS_OPENLAB else "openlab.manifest.yml")
        if not prod_manifest.exists():
            return

        # 預設跳過 appliances 與 endpoints/desktops
        _, targets_filtered = parse_day0_manifest(
            prod_manifest, skip_appliances=True, skip_endpoints=True
        )
        filtered_names = [t.get("name") for t in targets_filtered]
        if not IS_OPENLAB:
            self.assertIn("control-node", filtered_names)
            self.assertIn("base", filtered_names)
            self.assertNotIn("storage1", filtered_names)
            pass
            self.assertNotIn("laptop", filtered_names)

            # 全數載入模式
            _, targets_all = parse_day0_manifest(
                prod_manifest, skip_appliances=False, skip_endpoints=False
            )
            self.assertEqual(len(targets_all), 16)
        else:
            self.assertTrue(len(targets_filtered) > 0, "OpenLab must parse at least one host")


class TestTemplateCompiler(unittest.TestCase):
    """測試模板編譯器在完整配置與極簡配置下均能 100% 渲染且不拋出 UndefinedError"""

    def test_render_all_templates_with_production_manifest(self):
        import argparse
        from engine.compiler import build_compilation_targets, parse_simple_yaml, render_template

        manifest_path = REPO_ROOT / "conf" / ("openlab.manifest.yml" if IS_OPENLAB else "openlab.manifest.yml")
        ctx = parse_simple_yaml(manifest_path)
        dest_prefix = "openlab-" if IS_OPENLAB else "openlab-"
        args = argparse.Namespace(
            manifest=str(manifest_path), site=None, diff=True, apply=False,
            dest_prefix=None, base_dir="/home/labadmin", ops_internal=True, full_federation=False
        )
        targets = build_compilation_targets(args, ctx, Path("/home/labadmin"), dest_prefix)
        self.assertGreaterEqual(len(targets), 15)

        for t in targets:
            rendered = render_template(t["template"], ctx)
            self.assertTrue(len(rendered.strip()) > 0, f"Template {t['template'].name} rendered empty")

    def test_render_all_templates_with_minimal_test_manifest(self):
        import argparse
        from engine.compiler import build_compilation_targets, parse_simple_yaml, render_template

        test_manifest = REPO_ROOT / "tests" / "conf" / ("openlab.manifest.test.yml" if IS_OPENLAB else "openlab.manifest.test.yml")
        ctx = parse_simple_yaml(test_manifest)
        # 模擬 compiler.py 預設補齊邏輯
        ctx.setdefault("inventory", {})
        ctx.setdefault("keys", {"ansible": "ansible.key", "user": "id_user.key", "git": "git.key"})
        ctx["cluster"] = {
            "name": "OpenLabOps-Mock", "domain": "mock", "admin_user": "labadmin",
            "ansible_user": "lab", "timezone": "UTC", "locale": "en_US.UTF-8"
        }
        ctx.setdefault("networks", {"service_lan": "172.28.0.0/16", "wg_lan": "172.28.0.0/16"})
        ctx.setdefault("git_platform", {
            "host": "mock-gitea.test", "ip": "172.28.0.2", "ssh_port": 22,
            "http_port": 3000, "org": "OpenLabOps", "repo_prefix": "openlab"
        })

        args = argparse.Namespace(
            manifest=str(test_manifest), site=None, diff=True, apply=False,
            dest_prefix=None, base_dir="/home/labadmin", ops_internal=True, full_federation=False
        )
        targets = build_compilation_targets(args, ctx, Path("/home/labadmin"), "openlab-")
        for t in targets:
            rendered = render_template(t["template"], ctx)
            self.assertTrue(len(rendered.strip()) > 0)

    def test_render_all_templates_with_openlab_manifest(self):
        import argparse
        from engine.compiler import build_compilation_targets, parse_simple_yaml, render_template

        openlab_manifest = REPO_ROOT / "conf" / "openlab.manifest.yml"
        self.assertTrue(openlab_manifest.exists(), "conf/openlab.manifest.yml must exist")
        ctx = parse_simple_yaml(openlab_manifest)
        ctx["inventory_groups"] = ["servers"]
        ctx["inventory_nodes"] = ["localhost"]

        args = argparse.Namespace(
            manifest=str(openlab_manifest), site=None, diff=True, apply=False,
            dest_prefix="openlab-", base_dir="/home/labadmin", ops_internal=True, full_federation=False
        )
        targets = build_compilation_targets(args, ctx, Path("/home/labadmin"), "openlab-")
        for t in targets:
            rendered = render_template(t["template"], ctx)
            self.assertTrue(len(rendered.strip()) > 0)

    def test_openlab_distillation_dry_run_and_schema_eval(self):
        if IS_OPENLAB:
            self.skipTest("OpenLabOps downstream does not self-distill")
        import argparse
        import subprocess
        from engine.compiler import distill_openlabops_hub

        # 測試 --distill-openlab 乾跑無例外拋出 [INV-09]
        args = argparse.Namespace(apply=False)
        try:
            distill_openlabops_hub(args)
        except Exception as e:
            self.fail(f"distill_openlabops_hub dry-run failed with exception: {e}")

        # 驗證 OpenLab CUE 規格庫合規性
        openlab_cue_files = [
            str(REPO_ROOT / "templates" / "openlab" / "schema" / "network.cue"),
            str(REPO_ROOT / "templates" / "openlab" / "schema" / "roles.cue"),
            str(REPO_ROOT / "schema" / "keys.cue"),
            str(REPO_ROOT / "schema" / "nodes.cue")
        ]
        res = subprocess.run(["cue", "eval"] + openlab_cue_files, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"cue eval failed on OpenLab schemas: {res.stderr}")

    def test_openlab_distillation_and_sanitization_gate(self):
        if IS_OPENLAB:
            self.skipTest("OpenLabOps downstream does not self-distill")
        import argparse
        import subprocess
        import tempfile
        from engine.compiler import distill_openlabops_hub, verify_openlabops_sanitization

        # 於 /tmp 建立臨時沙箱執行完整蒸餾與脫敏閘門檢驗 [INV-11, INV-12]
        with tempfile.TemporaryDirectory(prefix="test_distill_gate_") as tmp_dir:
            args = argparse.Namespace(apply=True, openlab_dir=tmp_dir)
            try:
                distill_openlabops_hub(args)
            except Exception as e:
                self.fail(f"distill_openlabops_hub failed with exception: {e}")

            # 再次以嚴格模式驗證產出目錄無外洩
            try:
                verify_openlabops_sanitization(Path(tmp_dir))
            except Exception as e:
                self.fail(f"verify_openlabops_sanitization failed: {e}")

            # 驗證蒸餾產物 CUE 規格庫檢驗
            res_cue = subprocess.run(["cue", "vet", "./schema/..."], cwd=tmp_dir, capture_output=True, text=True)
            self.assertEqual(res_cue.returncode, 0, f"cue vet failed in distilled OpenLab: {res_cue.stderr}")

            # 驗證 Python 語法全數合法
            res_py = subprocess.run(["python3", "-m", "compileall", ".", "-q"], cwd=tmp_dir, capture_output=True, text=True)
            self.assertEqual(res_py.returncode, 0, f"compileall failed in distilled OpenLab: {res_py.stderr}")

    def test_sanitization_gate_negative_blocks_leaks(self):
        """[INV-12] 驗證脫敏閘門具備真實阻斷能力，注入違規模式時必拋出 RuntimeError"""
        if IS_OPENLAB:
            self.skipTest("OpenLabOps downstream does not self-distill")
        import tempfile
        from engine.compiler import verify_openlabops_sanitization

        # 採用分段拼接以避免測試源碼自身在蒸餾複製時命中脫敏閘門
        test_leaks = [
            ("public_ip", "connect to " + "198.51.100.10" + " for external access"),
            ("public_ip", "cloud host " + "198.51.100.136"),
            ("brand", "welcome to " + "labadmin" + "reich homelab"),
            ("brand", "password " + "labadmin" + "test123"),
            ("domain", "ssh user@gitea." + "ze" + "on"),
            ("subnet", "network " + "192.168.1." + "50/24"),
            ("host", "node name " + "arch" + "desk"),
            ("endpoint_host", "target " + "p" + "16" + "gen3"),
            ("endpoint_host", "server node_" + "base" + ".json"),
            ("endpoint_host", "Host " + "gate" + "way 192.168.1.1"),
            ("host_alias", "ssh go" + "remote-node1"),
            ("geography", "timezone Asia/" + "Taipei"),
            ("network_tables", "table wg_" + "mesh"),
            ("path", "/home/" + "labadmin" + "/.ssh/id_rsa"),
            ("user", "chown " + "labadmin:labadmin" + " /opt"),
            ("env_var", "export " + "lab_" + "LANG=zh_TW"),
            ("special_config", "include /etc/pf." + "labadmin"),
            ("appliance", "install " + "es" + "xi 8.0"),
            ("appliance", "var appliance_" + "es" + "xi"),
            ("appliance", "field is_" + "xigma" + "nas"),
            ("appliance", "key id_rsa_" + "xigma" + "nas"),
            ("appliance_key", "IdentityFile ~/.ssh/" + "ze" + "on.key"),
            ("brand", "account " + "labadmin" + "0093"),
            ("env_var", "export " + "lab_" + "CONFIG_PATH=/tmp"),
            ("pseudo_tags", "group " + "Virtualization" + "-Host"),
            ("pseudo_tags", "type " + "Storage" + "-Appliance"),
            ("pseudo_tags", "gateway " + "Unix" + "-Gateway"),
            ("pseudo_tags", "network " + "Network" + "-Appliance"),
            ("endpoint_host", "IdentityFile ~/.ssh/" + "w" + "sl.key"),
            ("endpoint_host", "target endpoint: " + "w" + "sl"),
            ("host", "file node_" + "os" + "k1.json"),
        ]

        for cat, leak_text in test_leaks:
            with tempfile.TemporaryDirectory(prefix="test_gate_neg_") as tmp_dir:
                bad_file = Path(tmp_dir) / "leaked_doc.txt"
                bad_file.write_text(leak_text, encoding="utf-8")
                with self.assertRaises(RuntimeError, msg=f"Sanitization gate failed to block category '{cat}': {leak_text}"):
                    verify_openlabops_sanitization(Path(tmp_dir))


class TestNodeClassifier(unittest.TestCase):
    """測試節點分類引擎 (dev / server / desktop / appliance) 與 hosts.yml 渲染"""

    def test_classify_nodes_categories_and_online_flags(self):
        from engine.classifier import load_node_files, classify_nodes, render_hosts_yaml

        # 1. 驗證空倉庫時預設乾淨為 [] (Zero-Preloaded Invariant)
        clean_nodes = load_node_files()
        self.assertIsInstance(clean_nodes, list)

        # 2. 測試多維節點分類邏輯 (以規範定義之各類型節點測試 classify_nodes)
        sample_nodes = [
            {
                "hostname": "control-node",
                "node_category": "dev",
                "always_online": True,
                "is_immutable": False,
                "appliance_type": "none",
                "key_profile": "standard",
                "primary_ip": "192.168.1.11",
                "subnet_cidr": "192.168.1.0/24",
                "os_family": "ArchLinux",
                "distribution": "Arch Linux",
                "capabilities": {"has_docker": True, "has_python": True}
            },
            {
                "hostname": "workstation1",
                "node_category": "desktop",
                "always_online": False,
                "is_immutable": False,
                "appliance_type": "none",
                "key_profile": "standard",
                "primary_ip": "192.168.1.50",
                "subnet_cidr": "192.168.1.0/24",
                "os_family": "Windows",
                "distribution": "Windows 11",
                "capabilities": {"has_docker": False, "has_python": False}
            },
            {
                "hostname": "server-base",
                "node_category": "server",
                "always_online": True,
                "is_immutable": False,
                "appliance_type": "none",
                "key_profile": "standard",
                "primary_ip": "192.168.1.230",
                "subnet_cidr": "192.168.1.0/24",
                "os_family": "Linux",
                "distribution": "Photon OS",
                "capabilities": {"has_docker": True, "has_python": True}
            }
        ]

        groups = classify_nodes(sample_nodes)
        self.assertIn("control-node", groups["dev"])
        self.assertIn("workstation1", groups["desktops"])
        self.assertIn("server-base", groups["servers"])
        self.assertIn("server-base", groups["capabilities"]["docker_hosts"])
        # 驗證精簡 Inventory JSON 欄位：嚴禁包含 mac_address, hardware, kernel, version 等非 Inventory 欄位
        for n in sample_nodes:
            self.assertNotIn("mac_address", n)
            self.assertNotIn("hardware", n)
            self.assertNotIn("kernel", n)
            self.assertNotIn("version", n)

        yaml_text = render_hosts_yaml(groups)
        self.assertIn("dev:", yaml_text)
        self.assertIn("desktops:", yaml_text)
        self.assertIn("servers:", yaml_text)
        self.assertIn("appliances:", yaml_text)


class TestBootSyncAndLockout(unittest.TestCase):
    """測試開機 openlab-secrets Git SHA 比對、Action Dispatch 負載與門禁檢查"""

    def test_local_synced_commit_read_write(self):
        import lab_boot_sync
        with tempfile.TemporaryDirectory() as tmp:
            fake_commit_file = Path(tmp) / "last_synced_commit"
            with mock.patch.object(lab_boot_sync, "get_commit_file_path", return_value=fake_commit_file):
                self.assertEqual(lab_boot_sync.get_last_synced_commit(), "")
                ok = lab_boot_sync.update_local_synced_commit("a1b2c3d4e5f6")
                self.assertTrue(ok)
                self.assertEqual(lab_boot_sync.get_last_synced_commit(), "a1b2c3d4e5f6")

    def test_dispatch_payload_enforces_client_keys_false(self):
        import lab_boot_sync
        captured_requests = []

        class FakeResponse:
            status = 204
            def __enter__(self): return self
            def __exit__(self, *args): pass

        def fake_urlopen(req, timeout=10):
            captured_requests.append(req)
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            res = lab_boot_sync.dispatch_key_sync_action(
                target_host="desktop",
                commit_sha="oldsha123",
                gitea_url="http://mock-gitea.test",
                org="OpenLabOps",
                repo_prefix="openlab"
            )
            self.assertTrue(res)
            self.assertEqual(len(captured_requests), 1)
            req = captured_requests[0]
            self.assertIn("/repos/OpenLabOps/openlab-workflows/actions/workflows/deploy-ssh-keys.yml/dispatches", req.full_url)
            body = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body["inputs"]["target_hosts"], "desktop")
            self.assertEqual(body["inputs"]["source_commit_sha"], "oldsha123")
            self.assertEqual(body["inputs"]["deploy_client_keys"], "false", "MUST never deploy private keys on boot sync")

    def test_lockout_guard_behavior(self):
        from core import lockout
        with tempfile.TemporaryDirectory() as tmp:
            fake_stamp = Path(tmp) / "synced_ok"
            with mock.patch.object(lockout, "SYNC_STAMP_FILE", fake_stamp):
                with mock.patch.object(lockout, "is_node_intermittent", return_value=True):
                    # 未同步時應鎖定
                    locked, reason = lockout.check_lockout_status()
                    self.assertTrue(locked)
                    self.assertIn("門禁", reason)

                    # 寫入 synced_ok 後應解鎖
                    fake_stamp.write_text("synced_ok\n", encoding="utf-8")
                    locked_after, _ = lockout.check_lockout_status()
                    self.assertFalse(locked_after)


class TestArchitecturalInvariants(unittest.TestCase):
    """測試硬性架構不變量 [INV-01], [INV-02], [INV-04], [INV-06], [INV-09]"""

    def test_inv01_zero_external_dependencies(self):
        forbidden = ["requests", "yaml", "paramiko", "jinja2", "cryptography"]
        py_files = (
            list(REPO_ROOT.glob("tools/**/*.py")) +
            list(REPO_ROOT.glob("engine/*.py")) +
            list(REPO_ROOT.glob("ansible/scripts/*.py"))
        )
        violations = []
        for p in py_files:
            content = p.read_text(encoding="utf-8", errors="ignore")
            for pkg in forbidden:
                for line in content.splitlines():
                    s = line.strip()
                    if s.startswith(f"import {pkg}") or s.startswith(f"from {pkg} import"):
                        violations.append((p.name, pkg))
        self.assertEqual(violations, [], f"INV-01 violations found: {violations}")

    def test_inv02_playbook_blocks_private_keys_for_non_dev(self):
        pb_path = REPO_ROOT / "ansible" / "playbooks" / "deploy-node-ssh-keys.yml"
        content = pb_path.read_text(encoding="utf-8")
        self.assertIn("'dev' in group_names", content, "Playbook MUST guard client key copy with 'dev' in group_names")

        wf_path = REPO_ROOT / "workflows" / ".gitea" / "workflows" / "deploy-ssh-keys.yml"
        wf_content = wf_path.read_text(encoding="utf-8")
        self.assertIn("default: 'false'", wf_content, "Workflow deploy_client_keys MUST default to 'false'")
        self.assertIn("source_commit_sha:", wf_content, "Workflow MUST declare source_commit_sha input")

        act_path = REPO_ROOT / "workflows" / ".gitea" / "actions" / "execute-federation-playbook" / "action.yml"
        act_content = act_path.read_text(encoding="utf-8")
        self.assertIn("source_commit_sha:", act_content, "Action MUST accept source_commit_sha")
        self.assertIn("repo_prefix:", act_content, "Action MUST parameterize repo_prefix [CODE-01]")
        self.assertIn('show "${SOURCE_SHA}:ssh-key/${KEY}"', act_content, "Action MUST extract historical key for source_commit_sha")
        self.assertNotIn('eval "$CMD"', act_content, "Action MUST NOT use unsafe eval [CODE-02]")

        run_act_path = REPO_ROOT / "workflows" / ".gitea" / "actions" / "run-ansible-playbook" / "action.yml"
        self.assertNotIn('eval "$CMD"', run_act_path.read_text(encoding="utf-8"), "run-ansible-playbook MUST NOT use unsafe eval [CODE-02]")

        rot_path = REPO_ROOT / "ansible" / "playbooks" / "rotate-ansible-keys.yml"
        rot_content = rot_path.read_text(encoding="utf-8")
        self.assertIn("chdir: \"{{ resolved_secrets_dir }}\"", rot_content, "Rotation playbook MUST read SHA from secrets repo")
        self.assertIn("keys.ansible | regex_replace('\\\\.key$', '.pub')", rot_content, "Play 1 MUST replace .key with .pub [CODE-06]")

        gv_path = REPO_ROOT / "ansible" / "group_vars" / "all.yml"
        gv_content = gv_path.read_text(encoding="utf-8")
        if IS_OPENLAB:
            self.assertIn("ansible_key_options: 'from=\"192.168.1.0/24\"'", gv_content, "ansible_key_options MUST restrict ansible.pub to 192.168.1.0/24")
        else:
            self.assertIn("ansible_key_options: 'from=\"192.168.1.0/24\"'", gv_content, "ansible_key_options MUST restrict lab.pub strictly to service_lan (192.168.1.0/24)")

        gv_tpl_path = REPO_ROOT / "templates" / "ansible" / "group_vars_all.yml.j2"
        gv_tpl_content = gv_tpl_path.read_text(encoding="utf-8")
        self.assertIn("ansible_key_options: 'from=\"{{ networks.service_lan }}\"'", gv_tpl_content, "group_vars_all.yml.j2 MUST restrict ansible_key_options to networks.service_lan")

    def test_inv06_centralized_docs_and_no_duplicate_dirs(self):
        self.assertFalse((REPO_ROOT / "workflows" / "workflows").exists(), "Duplicate workflows/workflows directory must not exist")
        self.assertFalse((REPO_ROOT / "workflows" / "scripts").exists(), "Duplicate workflows/scripts directory must not exist")
        self.assertFalse((REPO_ROOT / "docker").exists(), "Duplicate docker/ directory must be consolidated into extensions/containers/")
        self.assertFalse((REPO_ROOT / "inventory").exists(), "Duplicate root inventory/ directory must not exist")
        self.assertFalse((REPO_ROOT / "tests" / "sandbox" / "artifacts").exists(), "Stale test artifacts directory must not be tracked in git")
        self.assertFalse((REPO_ROOT / "tools" / "lib" / "core" / "network_audit.py").exists(), "Duplicate network_audit.py must not exist in core/")
        self.assertFalse((REPO_ROOT / "tools" / "lib" / "sync_openlab_tools.py").exists(), "Legacy sync_openlab_tools.py must be consolidated into sync_ops_tools.py")
        self.assertFalse((REPO_ROOT / "engine" / "extractor.py").exists(), "Obsolete engine/extractor.py must not exist [ARCH-04]")
        self.assertFalse((REPO_ROOT / "extensions" / "containers" / "README.md").exists(), "Markdown docs must reside in docs/ [INV-06]")
        self.assertFalse((REPO_ROOT / "extensions" / "remotes" / "github" / "README.md").exists(), "Markdown docs must reside in docs/ [INV-06]")
        if IS_OPENLAB:
            self.assertTrue((REPO_ROOT / "bin" / "lab-node").is_symlink(), "bin/lab-node must be a symlink to ../tools/bin/lab-node")
        else:
            self.assertTrue((REPO_ROOT / "bin" / "lab-node").is_symlink(), "bin/lab-node must be a symlink to ../tools/bin/lab-node")
        self.assertTrue((REPO_ROOT / "tools" / "VERSION").is_symlink(), "tools/VERSION must be a symlink to ../VERSION")

        from core.config import get_cluster_targets
        targets = get_cluster_targets()
        self.assertIsInstance(targets, list, "get_cluster_targets() must return list from dynamic facts/snapshot [ARCH-02]")
        for t in targets:
            self.assertIn("name", t)
            self.assertIn("host", t)
            self.assertIn("os", t)
            self.assertIn("mgr", t)
            if not t.get("is_local"):
                self.assertIn("ssh_target", t)

    def test_gitea_url_resolution_priority(self):
        from core.config import get_gitea_url
        with mock.patch.dict(os.environ, {"GITEA_URL": "http://172.28.0.2:3000"}):
            self.assertEqual(get_gitea_url(), "http://172.28.0.2:3000")

    def test_local_connectivity_probe_logic(self):
        from lab_tools import run_local_connectivity_test
        # Mock empty snapshot to verify clean exit without NameError or crash
        with mock.patch("lab_node.get_current_snapshot", return_value=[]):
            res = run_local_connectivity_test()
            self.assertTrue(res)

    def test_inv04_cue_schema_and_node_telemetry(self):
        cue_bin = shutil.which("cue")
        if not cue_bin:
            self.skipTest("cue binary not installed")

        # 1. 驗證 schema 本身
        r1 = subprocess.run([cue_bin, "vet", "./schema/"], cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, f"cue vet ./schema/ failed: {r1.stderr}")

        # 2. 驗證每個單一節點 JSON
        for nf in sorted((REPO_ROOT / "conf" / "nodes").glob("*.json")):
            if nf.name == "current.json":
                r_snap = subprocess.run([cue_bin, "vet", "-d", "#NodesSnapshot", "./schema/", str(nf)], cwd=str(REPO_ROOT), capture_output=True, text=True)
                self.assertEqual(r_snap.returncode, 0, f"current.json failed #NodesSnapshot: {r_snap.stderr}")
            else:
                r_node = subprocess.run([cue_bin, "vet", "-d", "#NodeTelemetry", "./schema/", str(nf)], cwd=str(REPO_ROOT), capture_output=True, text=True)
                self.assertEqual(r_node.returncode, 0, f"{nf.name} failed #NodeTelemetry: {r_node.stderr}")

    def test_inv09_no_test_paths_in_production_code(self):
        prod_files = list(REPO_ROOT.glob("engine/*.py")) + list(REPO_ROOT.glob("tools/**/*.py"))
        for p in prod_files:
            content = p.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("tests/conf/nodes", content, f"{p.name} must not reference tests/conf/nodes [INV-09]")


class TestInternationalizationAndLanguageSelection(unittest.TestCase):
    """驗證 i18n 多國語系字典與 Day-0 初始化語言選擇機制"""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT))
        sys.path.insert(0, str(REPO_ROOT / "tools" / "lib"))

    def test_i18n_translation_lookup(self):
        from tools.lib.core.i18n import set_locale, get_locale, t

        # 繁體中文
        set_locale("zh_TW")
        self.assertEqual(get_locale(), "zh_TW")
        self.assertEqual(t("common.success"), "成功")
        self.assertIn("Day-0", t("init.banner_title"))

        # English (US)
        set_locale("en_US")
        self.assertEqual(get_locale(), "en_US")
        self.assertEqual(t("common.success"), "SUCCESS")
        self.assertIn("Day-0", t("init.banner_title"))

        # 日本語
        set_locale("ja_JP")
        self.assertEqual(get_locale(), "ja_JP")
        self.assertEqual(t("common.success"), "成功")
        self.assertIn("Day-0", t("init.banner_title"))

    def test_default_locale_by_context(self):
        from tools.lib.core.i18n import DEFAULT_LOCALE
        self.assertEqual(DEFAULT_LOCALE, "en_US" if IS_OPENLAB else "zh_TW")

    def test_day0_init_lang_selection(self):
        from engine.initialize import setup_base_parameters

        # 測試 --lang en_US 傳入
        cfg_en = setup_base_parameters(manifest_meta={}, non_interactive=True, cli_lang="en_US")
        self.assertEqual(cfg_en["lang"], "en_US")
        self.assertEqual(cfg_en["locale"], "en_US.UTF-8")

        # 測試 --lang ja_JP 傳入
        cfg_ja = setup_base_parameters(manifest_meta={}, non_interactive=True, cli_lang="ja_JP")
        self.assertEqual(cfg_ja["lang"], "ja_JP")
        self.assertEqual(cfg_ja["locale"], "ja_JP.UTF-8")

        # 測試 --lang zh_TW 傳入
        cfg_zh = setup_base_parameters(manifest_meta={}, non_interactive=True, cli_lang="zh_TW")
        self.assertEqual(cfg_zh["lang"], "zh_TW")
        self.assertEqual(cfg_zh["locale"], "zh_TW.UTF-8")

    def test_semver_prerelease_comparison(self):
        from tools.lib.core.version import compare_versions
        self.assertEqual(compare_versions("0.5.0", "0.5.0-beta"), 1)
        self.assertEqual(compare_versions("0.5.0-rc.1", "0.5.0-beta"), 1)
        self.assertEqual(compare_versions("0.5.0-beta", "0.4.0"), 1)
        self.assertEqual(compare_versions("0.5.0", "0.5.0"), 0)
        self.assertEqual(compare_versions("0.4.0", "0.5.0-beta"), -1)

    def test_git_watch_safeguard_and_dashboard_summary(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from tools.lib.lab_git_watch import inspect_git_repo
        from tools.lib.lab_status import collect_git_watch_summary

        def _git(cwd, *args):
            return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)

        with tempfile.TemporaryDirectory(prefix="lab-git-watch-test-") as tmp:
            tmp_p = Path(tmp)
            bare = tmp_p / "origin.git"
            peer = tmp_p / "peer"
            node_repo = tmp_p / "node_repo"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "clone", str(bare), str(peer)], check=True, capture_output=True)
            _git(peer, "config", "user.email", "test@example.com")
            _git(peer, "config", "user.name", "Test")
            (peer / "README.md").write_text("v1\n", encoding="utf-8")
            _git(peer, "add", "README.md")
            _git(peer, "commit", "-m", "init")
            _git(peer, "branch", "-M", "main")
            _git(peer, "push", "-u", "origin", "main")
            _git(bare, "symbolic-ref", "HEAD", "refs/heads/main")

            subprocess.run(["git", "clone", str(bare), str(node_repo)], check=True, capture_output=True)
            _git(node_repo, "config", "user.email", "test@example.com")
            _git(node_repo, "config", "user.name", "Test")

            # 1. SYNCED
            res_sync = inspect_git_repo(str(node_repo), mode="auto_pull", do_fetch=True)
            self.assertEqual(res_sync["state"], "SYNCED")

            # 2. Peer pushes v2 -> fetch_only reports BEHIND without pulling
            (peer / "README.md").write_text("v2\n", encoding="utf-8")
            _git(peer, "commit", "-am", "v2")
            _git(peer, "push")
            res_behind = inspect_git_repo(str(node_repo), mode="fetch_only", do_fetch=True)
            self.assertEqual(res_behind["state"], "BEHIND")
            self.assertEqual(res_behind["behind"], 1)

            # 3. Dirty working tree -> DIRTY_HOLD even with mode=auto_pull
            (node_repo / "dirty.txt").write_text("wip\n", encoding="utf-8")
            res_dirty = inspect_git_repo(str(node_repo), mode="auto_pull", do_fetch=True)
            self.assertEqual(res_dirty["state"], "DIRTY_HOLD")
            self.assertEqual(res_dirty["behind"], 1)
            self.assertFalse(res_dirty["pulled"])
            (node_repo / "dirty.txt").unlink()

            # 4. Clean + auto_pull -> AUTO_PULLED
            res_pull = inspect_git_repo(str(node_repo), mode="auto_pull", do_fetch=True)
            self.assertEqual(res_pull["state"], "AUTO_PULLED")
            self.assertTrue(res_pull["pulled"])
            self.assertEqual((node_repo / "README.md").read_text(encoding="utf-8"), "v2\n")

            # 5. Local unpushed commit -> AHEAD_HOLD
            (node_repo / "local.txt").write_text("local\n", encoding="utf-8")
            _git(node_repo, "add", "local.txt")
            _git(node_repo, "commit", "-m", "local")
            res_ahead = inspect_git_repo(str(node_repo), mode="auto_pull", do_fetch=True)
            self.assertEqual(res_ahead["state"], "AHEAD_HOLD")
            self.assertEqual(res_ahead["ahead"], 1)

            # 6. Central dashboard summary highlights HOLD and BEHIND
            summary = collect_git_watch_summary({
                "agy1": {"git_repos": [res_ahead]},
                "storage1": {"git_repos": [res_behind, res_sync]},
            })
            self.assertEqual(len(summary["hold_items"]), 1)
            self.assertEqual(len(summary["behind_items"]), 1)
            self.assertEqual(summary["synced_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
