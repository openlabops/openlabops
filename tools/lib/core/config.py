# -*- coding: utf-8 -*-
# OpenLabOps Tools Central Configuration Loader
# Zero-dependency standard library loader for tools.config.json

import os
import sys
import json
from pathlib import Path

LIB_CORE_DIR = Path(__file__).resolve().parent
TOOLS_ROOT = LIB_CORE_DIR.parent.parent
DEFAULT_CONF_PATH = TOOLS_ROOT / "conf" / "tools.config.json"

_config = None

def load_config() -> dict:
    global _config
    if _config is not None:
        return _config

    conf_path = os.environ.get("TOOLS_CONFIG", str(DEFAULT_CONF_PATH))
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                _config = json.load(f)
        except Exception:
            _config = {}
    else:
        _config = {}

    # Environment variable overrides
    if "GITEA_URL" in os.environ:
        _config.setdefault("gitea", {})["url"] = os.environ["GITEA_URL"]
    if "REPO_OWNER" in os.environ:
        _config.setdefault("gitea", {})["owner"] = os.environ["REPO_OWNER"]
    if "TOKEN_FILE" in os.environ:
        _config.setdefault("gitea", {})["token_file"] = os.environ["TOKEN_FILE"]

    return _config

def is_openlab() -> bool:
    """判斷當前執行環境是否為 OpenLabOps 開源模式"""
    if os.environ.get("LAB_MODE") == "1" or os.environ.get("GITEA_REPO_PREFIX") == "openlab":
        return True
    if any("lab-" in arg for arg in sys.argv):
        return True
    tools_dir = str(TOOLS_ROOT).lower()
    if "openlab" in tools_dir:
        return True
    if (TOOLS_ROOT.parent / "conf" / "openlab.manifest.yml").exists():
        return True
    if (TOOLS_ROOT.parent / "tests" / "conf" / "openlab.manifest.test.yml").exists():
        return True
    return False


def get_gitea_url() -> str:
    # 1. Environment variable override
    if "GITEA_URL" in os.environ and os.environ["GITEA_URL"].strip():
        return os.environ["GITEA_URL"].strip().rstrip("/")

    # 2. Local token/url persistent file
    url_candidates = [
        Path.home() / ".gitea_url",
        Path("/usr/local/bin/openlab/.gitea_url"),
        Path("/usr/local/bin/openlab/.gitea_url"),
    ]
    for uc in url_candidates:
        if uc.exists():
            try:
                u = uc.read_text(encoding="utf-8").strip()
                if u:
                    return u.rstrip("/")
            except Exception:
                pass

    # 3. Explicit configuration from tools.config.json
    cfg_url = load_config().get("gitea", {}).get("url")
    if cfg_url and cfg_url.strip() and cfg_url.strip() != "http://gitea.lab":
        return cfg_url.strip().rstrip("/")

    # 4. Declarative Manifest SSOT (openlab.manifest.yml or openlab.manifest.yml)
    if is_openlab():
        manifest_candidates = [
            TOOLS_ROOT.parent / "conf" / "openlab.manifest.yml",
            TOOLS_ROOT.parent / "tests" / "conf" / "openlab.manifest.test.yml",
            Path("/etc/openlab/openlab.manifest.yml"),
        ]
    else:
        manifest_candidates = [
            TOOLS_ROOT.parent / "conf" / "openlab.manifest.yml",
            TOOLS_ROOT.parent / "tests" / "conf" / "openlab.manifest.test.yml",
            Path("/etc/openlab/openlab.manifest.yml"),
        ]
    for mc in manifest_candidates:
        if mc.exists():
            try:
                lines = mc.read_text(encoding="utf-8").splitlines()
                in_gp = False
                gp_host, gp_port = "", ""
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("git_platform:"):
                        in_gp = True
                        continue
                    if in_gp:
                        if line and not line[0].isspace():
                            in_gp = False
                        elif stripped.startswith("host:"):
                            gp_host = stripped.split(":", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("http_port:"):
                            gp_port = stripped.split(":", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("url:"):
                            return stripped.split(":", 1)[1].strip().strip('"\'').rstrip("/")
                    elif stripped.startswith("gitea_url:"):
                        return stripped.split(":", 1)[1].strip().strip('"\'').rstrip("/")
                if gp_host:
                    port_str = f":{gp_port}" if gp_port and gp_port not in ("80", "443") else ""
                    return f"http://{gp_host}{port_str}"
            except Exception:
                pass

    return cfg_url or "http://gitea.lab"


def get_git_origin_info() -> tuple:
    """從當前或已知 Git 工作區的 origin remote URL 解析 (owner, repo)"""
    import subprocess
    import re
    sudo_user = os.environ.get("SUDO_USER", "")
    user_home = Path(f"/home/{sudo_user}") if sudo_user else Path.home()
    candidates = [
        Path.cwd(),
        TOOLS_ROOT.parent,
        user_home / "openlabops",
        user_home / "openlabops",
    ]
    for cand in candidates:
        if not (cand / ".git").exists():
            continue
        try:
            res = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=str(cand), capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                url = res.stdout.strip()
                m = re.search(r'[:/]([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$', url)
                if m:
                    return m.group(1), m.group(2)
        except Exception:
            pass
    return "", ""


def get_manifest_path() -> Path:
    """獲取當前環境之 Tier 2 站點宣告檔路徑 (openlab.manifest.yml 或 openlab.manifest.yml)"""
    if is_openlab():
        candidates = [
            TOOLS_ROOT.parent / "conf" / "openlab.manifest.yml",
            TOOLS_ROOT.parent / "tests" / "conf" / "openlab.manifest.test.yml",
            Path("/etc/openlab/openlab.manifest.yml"),
            Path.home() / ".config" / "openlab" / "openlab.manifest.yml",
        ]
    else:
        candidates = [
            TOOLS_ROOT.parent / "conf" / "openlab.manifest.yml",
            TOOLS_ROOT.parent / "tests" / "conf" / "openlab.manifest.test.yml",
            Path("/etc/openlab/openlab.manifest.yml"),
            Path.home() / ".config" / "openlab" / "openlab.manifest.yml",
        ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def get_manifest_value(section: str, key: str) -> str:
    """從 Tier 2 站點宣告檔中安全解析指定區塊與鍵值 (零第三方依賴純字串解析)"""
    p = get_manifest_path()
    if not p or not p.exists():
        return ""
    try:
        try:
            from core.yaml_parser import parse_scalar
        except ImportError:
            from .yaml_parser import parse_scalar
        lines = p.read_text(encoding="utf-8").splitlines()
        in_section = False
        target_sec = f"{section}:"
        target_key = f"{key}:"
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(target_sec):
                in_section = True
                continue
            if in_section:
                if line and not line[0].isspace():
                    in_section = False
                elif stripped.startswith(target_key):
                    val = stripped.split(":", 1)[1]
                    res = parse_scalar(val)
                    return "" if res is None else str(res)
    except Exception:
        pass
    return ""


def get_cluster_name() -> str:
    """取得叢集宣告名稱 (如 'OpenLabOps' 或 'OpenLab')"""
    env_c = os.environ.get("CLUSTER_NAME")
    if env_c and env_c.strip():
        return env_c.strip()
    val = get_manifest_value("cluster", "name")
    if val:
        return val
    cfg_name = load_config().get("cluster", {}).get("name")
    if cfg_name and cfg_name.strip():
        return cfg_name.strip()
    return "OpenLab" if is_openlab() else "OpenLabOps"


def get_admin_user() -> str:
    """取得站點系統管理員帳號 (由 lab-init 收集並落地於 manifest cluster.admin_user)"""
    env_u = os.environ.get("ADMIN_USER") or os.environ.get("GITEA_USER")
    if env_u and env_u.strip():
        return env_u.strip()
    val = get_manifest_value("cluster", "admin_user")
    if val:
        return val
    cfg_user = load_config().get("cluster", {}).get("admin_user") or load_config().get("gitea", {}).get("admin_user")
    if cfg_user and cfg_user.strip():
        return cfg_user.strip()
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return "admin" if is_openlab() else "labadmin"


def get_ansible_user() -> str:
    """取得站點 Ansible 自動化運維主帳號 (由 lab-init 收集並落地於 manifest cluster.ansible_user)"""
    env_u = os.environ.get("ANSIBLE_USER")
    if env_u and env_u.strip():
        return env_u.strip()
    val = get_manifest_value("cluster", "ansible_user")
    if val:
        return val
    cfg_user = load_config().get("cluster", {}).get("ansible_user")
    if cfg_user and cfg_user.strip():
        return cfg_user.strip()
    return "ansible" if is_openlab() else "lab"


def get_repo_owner() -> str:
    """取得 Gitea 組織名稱 (由 lab-init 收集並落地於 manifest git_platform.org)"""
    # 1. Environment variable override
    env_owner = os.environ.get("GITEA_ORG") or os.environ.get("GITEA_OWNER") or os.environ.get("REPO_OWNER")
    if env_owner and env_owner.strip():
        return env_owner.strip()

    # 2. Declarative Manifest SSOT (git_platform.org)
    val = get_manifest_value("git_platform", "org")
    if val:
        return val

    # 3. tools.config.json
    cfg_owner = load_config().get("gitea", {}).get("owner")
    if cfg_owner and cfg_owner.strip():
        return cfg_owner.strip()

    # 4. Origin remote from current working tree (fallback only)
    git_owner, _ = get_git_origin_info()
    if git_owner and git_owner.lower() not in ("git", "github", "gitlab", "root"):
        return git_owner

    return get_cluster_name()


def get_token_file() -> str:
    default_token = "/usr/local/bin/openlab/.gitea_token"
    configured = load_config().get("gitea", {}).get("token_file", default_token)
    if os.path.exists(configured):
        return configured
    user_token = os.path.expanduser("~/.gitea_token")
    if os.path.exists(user_token):
        return user_token
    return configured


def get_cluster_prefix() -> str:
    """取得當前集群/聯邦倉庫命名前綴 (由 lab-init 收集並落地於 manifest git_platform.repo_prefix)"""
    # 1. Environment variable override
    env_p = os.environ.get("GITEA_REPO_PREFIX") or os.environ.get("REPO_PREFIX")
    if env_p and env_p.strip():
        return env_p.strip()

    # 2. Declarative Manifest SSOT (git_platform.repo_prefix)
    val = get_manifest_value("git_platform", "repo_prefix")
    if val:
        return val

    # 3. Check tools.config.json repos
    wf_repo = load_config().get("gitea", {}).get("repos", {}).get("workflows", "")
    if wf_repo and "-" in wf_repo:
        return wf_repo.split("-")[0]

    # 4. Check installation directory name
    tools_dir_str = str(TOOLS_ROOT).lower()
    if "openlab" in tools_dir_str:
        return "openlab"

    # 5. Git origin info fallback
    _, git_repo = get_git_origin_info()
    if git_repo:
        if git_repo.startswith("openlab"):
            return "openlab"

    return "openlab"


def get_repo_name(key: str) -> str:
    # 1. Environment variable override
    env_repo = os.environ.get("GITEA_REPO")
    if env_repo:
        return env_repo.strip()

    # 2. If running inside operations repository itself and querying workflows/operations
    _, git_repo = get_git_origin_info()
    if key in ("workflows", "operations", "ops") and git_repo == "openlabops":
        return git_repo

    # 3. tools.config.json explicit mapping
    repos = load_config().get("gitea", {}).get("repos", {})
    if key in repos:
        return repos[key]

    # 4. Manifest / Cluster prefix
    prefix = get_cluster_prefix()
    if prefix:
        if key == "workflows":
            return f"{prefix}-workflows"
        elif key in ("operations", "ops"):
            return f"{prefix}-operations"
        elif key in ("configs", "cmdb"):
            return f"{prefix}-configs"
        elif key in ("secrets", "keys"):
            return f"{prefix}-secrets"
        elif key == "ansible":
            return f"{prefix}-ansible"
        elif key == "tools":
            return f"{prefix}-tools"

    return f"{get_cluster_prefix()}-{key}"

def get_path(key: str, default: str = "") -> str:
    val = load_config().get("paths", {}).get(key, default)
    if val and val.startswith("~"):
        return os.path.expanduser(val)
    return val

def get_cache_dir() -> Path:
    base = Path(os.environ.get("OPENLAB_CACHE_DIR", os.path.expanduser("~/.cache/openlab")))
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_node_info_dir() -> Path:
    # 1. Environment variable override
    if "NODE_INFO_DIR" in os.environ:
        p = Path(os.environ["NODE_INFO_DIR"])
        if p.exists():
            return p
    # 2. Local openlabops conf/nodes (Master SSOT)
    ops_nodes = TOOLS_ROOT.parent / "conf" / "nodes"
    if ops_nodes.exists() and any(ops_nodes.glob("*.json")):
        return ops_nodes
    # 3. Local sibling clone (legacy dev mode fallback)
    dev_sibling = TOOLS_ROOT.parent.parent / "openlab-configs" / "node-information"
    if dev_sibling.exists():
        return dev_sibling
    # 4. Standard user cache
    cache_path = get_cache_dir() / "node-information"
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path

def get_managed_keys() -> list:
    if is_openlab():
        return load_config().get("ssh", {}).get("managed_keys", [
            {"name": "ansible.key", "type": "ed25519", "desc": "Ansible 自動化金鑰"},
            {"name": "id_user.key", "type": "ed25519", "desc": "管理使用者金鑰"},
            {"name": "git.key", "type": "ed25519", "desc": "版控認證金鑰"},
        ])
    return load_config().get("ssh", {}).get("managed_keys", [
        {"name": "id_user.key", "type": "ed25519", "desc": "萬能管理金鑰"},
        
        {"name": "ansible.key", "type": "ed25519", "desc": "Ansible 自動化金鑰"},
        {"name": "git.key", "type": "ed25519", "desc": "版控認證金鑰"},
    ])

def get_endpoint_hosts() -> list:
    return load_config().get("ssh", {}).get("endpoint_hosts", ["workstation", "laptop"])

def _resolve_target_key_path(login_user: str) -> str:
    admin_u = get_admin_user()
    ansible_u = get_ansible_user()
    if login_user == admin_u:
        key_name = get_manifest_value("keys", "user") or "id_user.key"
    elif login_user == ansible_u:
        key_name = get_manifest_value("keys", "ansible") or "ansible.key"
    else:
        key_name = "ansible.key" if login_user == "root" else f"{login_user}.key"
    return f"~/.ssh/{key_name}"


def get_cluster_targets(include_remote_cache: bool = True) -> list:
    static_targets = load_config().get("cluster_targets", [])
    if not static_targets:
        manifest_path = get_manifest_path()
        if manifest_path and manifest_path.exists():
            try:
                from core.yaml_parser import parse_yaml_file, extract_manifest_hosts_metadata
                meta_map = extract_manifest_hosts_metadata(parse_yaml_file(manifest_path))
                for hname, m in meta_map.items():
                    host_ip = m.get("ip") or hname
                    t_user = m.get("user") or get_ansible_user()
                    k_name = m.get("key_name")
                    k_path = f"~/.ssh/{k_name}" if k_name else _resolve_target_key_path(t_user)
                    static_targets.append({
                        "name": hname,
                        "host": host_ip,
                        "os": "Linux",
                        "mgr": "generic",
                        "pkg_manager": "generic",
                        "role": m.get("category", "server"),
                        "appliance_type": "none",
                        "ssh_target": f"-i {k_path} {t_user}@{host_ip}",
                        "target_user": t_user,
                        "use_sudo": (t_user != "root"),
                        "is_local": (hname == "control-node" or host_ip in ("127.0.0.1", "localhost")),
                    })
            except Exception:
                pass
    if not static_targets:
        static_targets = [
            {"name": "control-node", "host": "localhost", "os": "Linux", "mgr": "generic", "is_local": True},
        ]
    for st in static_targets:
        if not st.get("is_local") and "ssh_target" not in st:
            t_user = st.get("target_user") or get_ansible_user()
            k_path = _resolve_target_key_path(t_user)
            st["ssh_target"] = f"-i {k_path} {t_user}@{st.get('host', st.get('name', 'localhost'))}"
    static_by_name = {t["name"].split(".")[0].lower(): t for t in static_targets if "name" in t}

    # 優先自目前專案 conf/nodes/*.json 即時動態載入目標清單，若無則與遠端聯邦快取比對同步
    nodes_dir = TOOLS_ROOT.parent / "conf" / "nodes"
    node_items = []
    if nodes_dir.exists():
        # 先讀各節點事實檔
        for nf in sorted(nodes_dir.glob("*.json")):
            if nf.name in ("current.json", "archive") or nf.name.startswith("."):
                continue
            try:
                data = json.loads(nf.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    node_items.append(data)
            except Exception:
                pass

    # 若無單獨節點事實檔，比對遠端與本機快取 (一樣不重抓，不一樣自動同步)
    if not node_items and include_remote_cache:
        try:
            from core.gitea_api import sync_remote_node_cache_if_needed
            synced_nodes, _, _ = sync_remote_node_cache_if_needed()
            if isinstance(synced_nodes, list) and synced_nodes:
                node_items = synced_nodes
        except Exception:
            pass

    # 備援：讀本機 current.json
    if not node_items and nodes_dir.exists():
        cur_snap = nodes_dir / "current.json"
        if cur_snap.exists():
            try:
                data = json.loads(cur_snap.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    node_items = data
            except Exception:
                pass

    if node_items:
        # 依短主機名去重 (避免同時存在 Base 與 base)
        deduped_items = {}
        for n in node_items:
            hname = str(n.get("hostname", "")).strip()
            if not hname:
                continue
            sk = hname.split(".")[0].lower()
            prev = deduped_items.get(sk)
            if prev is None or (n.get("hardware") and not prev.get("hardware")):
                deduped_items[sk] = n

        dynamic_targets = []
        for n in deduped_items.values():
            if not n.get("always_online", True):
                continue
            hname = n.get("hostname", "")
            if not hname:
                continue
            lookup_name = hname.replace("_", "-")
            os_fam = n.get("os_family", "Linux")
            dist = n.get("distribution", os_fam)
            app_type = n.get("appliance_type", "none")
            mgr = "apt"
            if os_fam == "ArchLinux" or "Arch" in dist:
                mgr = "pacman"
            elif os_fam == "PhotonOS" or "Photon" in dist:
                mgr = "tdnf"
            elif app_type == "storage":
                mgr = "firmware"
            elif app_type == "kvm" or os_fam == "Virtualization":
                mgr = "esxcli"
                mgr = "pkg"
            elif os_fam in ("RHEL", "CentOS", "Rocky", "AlmaLinux", "Fedora", "OracleLinux") or "Oracle" in dist:
                mgr = "dnf"
            elif os_fam == "Alpine" or "Alpine" in dist:
                mgr = "apk"
            elif os_fam in ("Debian", "Ubuntu") or "Debian" in dist or "Ubuntu" in dist:
                mgr = "apt"
            elif os_fam in ("Suse", "SUSE") or "suse" in dist.lower():
                mgr = "zypper"
            host_ip = n.get("primary_ip") or n.get("ansible_host", hname)
            target_user = n.get("ansible_user") or n.get("target_user")
            if not target_user:
                target_user = "ansible" if is_openlab() else "lab"

            if not is_openlab() and app_type == "storage":
                login_user = "root"
                key_path = "~/.ssh/ansible.key"
            elif not is_openlab() and (app_type == "kvm" or os_fam == "Virtualization"):
                login_user = "root"
            else:
                login_user = target_user
                key_path = _resolve_target_key_path(login_user)

            short_key = hname.split(".")[0].lower()
            st_override = static_by_name.get(short_key, {})
            if st_override.get("ssh_target") and not is_openlab() and app_type not in ("storage", "kvm"):
                eff_ssh_target = st_override["ssh_target"]
            else:
                eff_ssh_target = f"-i {key_path} {login_user}@{host_ip}"
            eff_use_sudo = st_override["use_sudo"] if "use_sudo" in st_override else (login_user != "root")

            dynamic_targets.append({
                "name": hname,
                "host": host_ip,
                "os": dist or os_fam,
                "mgr": mgr,
                "pkg_manager": mgr,
                "role": n.get("node_category", "server"),
                "appliance_type": app_type if not is_openlab() else "none",
                "ssh_target": eff_ssh_target,
                "target_user": login_user,
                "use_sudo": eff_use_sudo,
                "is_storage": False,
                "is_kvm": False,
                "is_local": (hname == "control-node" or host_ip in ("127.0.0.1", "localhost")),
            })
        if dynamic_targets:
            return dynamic_targets

    # 備援：若未處於專案源碼庫環境（如獨立端點環境），則自快照路徑載入
    snapshot_candidates = [
        TOOLS_ROOT / "conf" / "current.json",
        Path("/usr/local/bin/openlab/conf/current.json"),
    ]
    for snap in snapshot_candidates:
        if snap.exists():
            try:
                nodes = json.loads(snap.read_text(encoding="utf-8"))
                if isinstance(nodes, list) and nodes:
                    dynamic_targets = []
                    for n in nodes:
                        if not n.get("always_online", True):
                            continue
                        hname = n.get("hostname", "")
                        if not hname:
                            continue
                        lookup_name = hname.replace("_", "-")
                        os_fam = n.get("os_family", "Linux")
                        dist = n.get("distribution", os_fam)
                        app_type = n.get("appliance_type", "none")
                        mgr = "apt"
                        if os_fam == "ArchLinux" or "Arch" in dist:
                            mgr = "pacman"
                        elif os_fam == "PhotonOS" or "Photon" in dist:
                            mgr = "tdnf"
                        elif app_type == "storage":
                            mgr = "firmware"
                        elif app_type == "kvm" or os_fam == "Virtualization":
                            mgr = "vib"
                            mgr = "pkg"
                        elif os_fam == "RedHat" or any(x in dist for x in ("Oracle", "Rocky", "Alma", "RHEL")):
                            mgr = "dnf"
                        host_ip = n.get("primary_ip") or lookup_name
                        target_user = n.get("ansible_user") or n.get("target_user")
                        if not target_user:
                            target_user = "ansible" if is_openlab() else "lab"
                        login_user = ("root" if app_type in ("storage", "kvm") else target_user) if not is_openlab() else target_user
                        entry = {
                            "name": lookup_name,
                            "host": host_ip,
                            "os": dist or os_fam,
                            "mgr": mgr,
                            "pkg_manager": mgr,
                            "role": n.get("node_category", "server"),
                            "appliance_type": app_type if not is_openlab() else "none",
                            "ssh_target": f"-i {key_path} {login_user}@{host_ip}",
                            "target_user": login_user,
                            "use_sudo": (login_user != "root"),
                            "is_local": (lookup_name == "control-node" or host_ip in ("127.0.0.1", "localhost")),
                        }
                        if not is_openlab():
                            if app_type == "storage":
                                entry["is_storage"] = True
                            elif app_type == "kvm":
                                entry["is_kvm"] = True
                        dynamic_targets.append(entry)
                    if dynamic_targets:
                        return dynamic_targets
            except Exception:
                pass

    return static_targets
