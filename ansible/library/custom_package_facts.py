#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import annotations

DOCUMENTATION = """
module: custom_package_facts
short_description: Package information as facts with explicit/system tagging
description:
  - Return information about installed packages as facts, distinguishing between
    explicitly installed (user-installed) packages, pure dependencies, and system packages.
  - Supports Arch Linux (pacman) (pkg), PhotonOS (tdnf), and Oracle Linux / RHEL / Fedora (dnf/rpm).
options:
  manager:
    description:
      - The package manager(s) used by the system so we can query the package information.
    default: ['auto']
    type: list
    elements: str
  strategy:
    description:
      - Controls how the module queries the package managers on the system.
    choices: ['first', 'all']
    default: 'first'
    type: str
  filter_dependencies:
    description:
      - When set to true, only packages that were actively/explicitly installed (non-pure dependencies)
        will be included in the returned packages fact.
    default: false
    type: bool
  filter_system:
    description:
      - When set to true, base/core system packages are excluded from the returned packages fact.
    default: false
    type: bool
"""

import re
import shutil

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.locale import get_best_parsable_locale
from ansible.module_utils.common.text.converters import to_native, to_text

BASE_SYSTEM_PACKAGES = {
    'base', 'base-devel', 'basesystem', 'filesystem', 'glibc', 'glibc-common',
    'glibc-all-langpacks', 'coreutils', 'coreutils-common', 'bash', 'kernel',
    'kernel-uek', 'kernel-core', 'kernel-modules', 'kernel-tools', 'linux',
    'linux-esx', 'linux-firmware', 'systemd', 'systemd-libs', 'systemd-pam',
    'systemd-udev', 'initramfs', 'minimal', 'grub2', 'grub', 'grubby',
    'setup', 'shadow-utils', 'util-linux', 'util-linux-core', 'pcre2',
    'libselinux', 'libsemanage', 'audit', 'audit-libs', 'crypto-policies',
    'ca-certificates', 'tzdata', 'rpm', 'rpm-libs', 'dnf', 'tdnf', 'pkg',
    'microcode_ctl', 'authselect', 'polkit', 'sudo', 'openssh-server'
}


class BaseMgr:
    CLI = None

    def __init__(self, module):
        self.module = module
        self._cli = None

    def is_available(self):
        if self.CLI:
            self._cli = shutil.which(self.CLI)
            return bool(self._cli)
        return False

    def list_installed(self):
        raise NotImplementedError

    def get_package_details(self, item):
        raise NotImplementedError

    def get_upgrades(self):
        return []

    def get_packages(self):
        installed = {}
        for item in self.list_installed():
            details = self.get_package_details(item)
            if not details or 'name' not in details:
                continue
            if 'source' not in details:
                details['source'] = self.__class__.__name__.lower()
            name = details['name']
            if name not in installed:
                installed[name] = [details]
            else:
                installed[name].append(details)
        return installed


class PACMAN(BaseMgr):
    CLI = 'pacman'

    def __init__(self, module):
        super(PACMAN, self).__init__(module)
        self.aur_pkgs = set()

    def _load_aur(self):
        # Query foreign (AUR) packages using yay if available, otherwise pacman -Qmq
        yay_bin = shutil.which('yay')
        cmd = [yay_bin, '-Qmq'] if yay_bin else [self._cli, '-Qmq']
        rc, out, _ = self.module.run_command(cmd, handle_exceptions=False)
        if rc == 0 and out:
            self.aur_pkgs = set(out.strip().splitlines())

    def list_installed(self):
        self._load_aur()
        locale = get_best_parsable_locale(self.module)
        rc, out, err = self.module.run_command(
            [self._cli, '-Qi'],
            environ_update=dict(LC_ALL=locale),
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.split("\n\n")[:-1]

    def get_package_details(self, raw_block):
        details = {}
        last_key = None
        for line in raw_block.splitlines():
            m = re.match(r"^([\w ]*[\w]) +: (.*)", line)
            if m:
                last_key = m.group(1).strip()
                details[last_key] = m.group(2).strip()
            elif last_key:
                details[last_key] += " " + line.strip()

        name = details.get('Name')
        if not name:
            return None

        reason = details.get('Install Reason', '')
        is_explicit = 'explicit' in reason.lower()
        groups = details.get('Groups', '')
        is_system = name in BASE_SYSTEM_PACKAGES or 'base' in groups.lower().split()
        is_aur = name in self.aur_pkgs

        return {
            'name': name,
            'version': details.get('Version', ''),
            'arch': details.get('Architecture', ''),
            'category': groups if groups != 'None' else '',
            'description': details.get('Description', ''),
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'yay' if is_aur else 'pacman',
            'repo': 'aur' if is_aur else 'official',
        }

    def get_upgrades(self):
        upgrades = []
        if not self.aur_pkgs:
            self._load_aur()
        yay_bin = shutil.which('yay')
        cmd = [yay_bin, '-Qu'] if yay_bin else ['checkupdates']
        rc, out, _ = self.module.run_command(cmd, handle_exceptions=False)
        if rc == 0 and out:
            for line in out.strip().splitlines():
                m = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", line.strip())
                if m:
                    pkg_name, old_v, new_v = m.group(1), m.group(2), m.group(3)
                    is_aur = pkg_name in self.aur_pkgs
                    upgrades.append({
                        'name': pkg_name,
                        'current_version': old_v,
                        'new_version': new_v,
                        'source': 'yay' if is_aur else 'pacman',
                        'repo': 'aur' if is_aur else 'official',
                    })
        return upgrades


class YAY(BaseMgr):
    CLI = 'yay'

    def list_installed(self):
        # Query foreign/AUR packages explicitly via yay
        rc_m, out_m, _ = self.module.run_command([self._cli, '-Qmq'], handle_exceptions=False)
        if rc_m != 0 or not out_m:
            return []
        aur_pkgs = set(out_m.strip().splitlines())

        locale = get_best_parsable_locale(self.module)
        rc, out, _ = self.module.run_command(
            [self._cli, '-Qi'],
            environ_update=dict(LC_ALL=locale),
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            return []

        blocks = out.split("\n\n")[:-1]
        aur_blocks = []
        for b in blocks:
            for line in b.splitlines():
                if line.startswith('Name'):
                    pkg_name = line.split(':', 1)[1].strip()
                    if pkg_name in aur_pkgs:
                        aur_blocks.append(b)
                    break
        return aur_blocks

    def get_package_details(self, raw_block):
        details = {}
        last_key = None
        for line in raw_block.splitlines():
            m = re.match(r"^([\w ]*[\w]) +: (.*)", line)
            if m:
                last_key = m.group(1).strip()
                details[last_key] = m.group(2).strip()
            elif last_key:
                details[last_key] += " " + line.strip()

        name = details.get('Name')
        if not name:
            return None

        reason = details.get('Install Reason', '')
        is_explicit = 'explicit' in reason.lower()
        groups = details.get('Groups', '')
        is_system = name in BASE_SYSTEM_PACKAGES or 'base' in groups.lower().split()

        return {
            'name': name,
            'version': details.get('Version', ''),
            'arch': details.get('Architecture', ''),
            'category': groups if groups != 'None' else '',
            'description': details.get('Description', ''),
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'yay',
            'repo': 'aur',
        }

    def get_upgrades(self):
        upgrades = []
        rc, out, _ = self.module.run_command([self._cli, '-Qu'], handle_exceptions=False)
        if rc == 0 and out:
            for line in out.strip().splitlines():
                m = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", line.strip())
                if m:
                    upgrades.append({
                        'name': m.group(1),
                        'current_version': m.group(2),
                        'new_version': m.group(3),
                        'source': 'yay',
                        'repo': 'aur',
                    })
        return upgrades


class PKG(BaseMgr):
    CLI = 'pkg'
    atoms = ['name', 'version', 'origin', 'installed', 'automatic', 'arch', 'category', 'prefix', 'vital', 'comment']

    def list_installed(self):
        # %n: name, %v: version, %R: repo, %t: time, %a: automatic, %q: arch, %o: origin, %p: prefix, %V: vital, %c: comment
        rc, out, err = self.module.run_command(
            [self._cli, 'query', "%%%s" % '\t%'.join(['n', 'v', 'R', 't', 'a', 'q', 'o', 'p', 'V', 'c'])],
            handle_exceptions=False,
        )
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.splitlines()

    def get_package_details(self, line):
        parts = line.split('\t')
        if len(parts) < len(self.atoms):
            parts.extend([''] * (len(self.atoms) - len(parts)))
        pkg = dict(zip(self.atoms, parts))

        name = pkg.get('name')
        if not name:
            return None

        is_auto = bool(int(pkg.get('automatic', 0)))
        is_vital = bool(int(pkg.get('vital', 0)))
        is_system = is_vital or name in ('pkg',)

        category = pkg.get('category', '')
        if '/' in category:
            category = category.split('/', 1)[0]

        return {
            'name': name,
            'version': pkg.get('version', ''),
            'arch': pkg.get('arch', ''),
            'category': category,
            'origin': pkg.get('origin', ''),
            'description': pkg.get('comment', ''),
            'automatic': is_auto,
            'install_reason': 'dependency' if is_auto else 'explicit',
            'system': is_system,
            'source': 'pkg',
        }

    def get_upgrades(self):
        upgrades = []
        rc, out, _ = self.module.run_command([self._cli, 'upgrade', '-n'], handle_exceptions=False)
        if out:
            for line in out.splitlines():
                m = re.search(r"Upgrading\s+(\S+)\s+from\s+(\S+)\s+to\s+(\S+)", line)
                if m:
                    upgrades.append({
                        'name': m.group(1),
                        'current_version': m.group(2),
                        'new_version': m.group(3).rstrip('.'),
                        'source': 'pkg',
                    })
        return upgrades


class TDNF(BaseMgr):
    CLI = 'tdnf'

    def __init__(self, module):
        super(TDNF, self).__init__(module)
        self.explicit_pkgs = set()

    def _load_history(self):
        # Query tdnf history to find user explicitly installed packages
        rc, out, err = self.module.run_command([self._cli, 'history'], handle_exceptions=False)
        if rc == 0 and out:
            installed = set()
            for line in out.splitlines()[1:]:
                if len(line) > 45:
                    cmd = line[5:45].strip()
                    parts = cmd.split()
                    if len(parts) >= 2 and parts[0] in ('install', 'in'):
                        for p in parts[1:]:
                            if not p.startswith('-'):
                                installed.add(p)
                    elif len(parts) >= 2 and parts[0] in ('remove', 'rm', 'erase'):
                        for p in parts[1:]:
                            installed.discard(p)
            self.explicit_pkgs = installed

    def list_installed(self):
        self._load_history()
        # Query RPM database
        rc, out, err = self.module.run_command(
            ['rpm', '-qa', '--qf', '%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\t%{GROUP}\t%{SUMMARY}\n'],
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            raise Exception("Unable to list rpm packages rc=%s : %s" % (rc, err))
        return out.strip().split('\n')

    def get_package_details(self, line):
        parts = line.split('\t')
        if len(parts) < 5:
            return None
        name, version, arch, group, summary = parts[0], parts[1], parts[2], parts[3], parts[4]

        # Check if explicitly installed in tdnf history
        is_explicit = name in self.explicit_pkgs or any(name.startswith(p) for p in self.explicit_pkgs)
        is_system = name in BASE_SYSTEM_PACKAGES

        return {
            'name': name,
            'version': version,
            'arch': arch,
            'category': group if group != '(none)' else '',
            'description': summary if summary != '(none)' else '',
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'tdnf',
        }

    def get_upgrades(self):
        upgrades = []
        rc, out, _ = self.module.run_command([self._cli, 'check-update', '-q'], handle_exceptions=False)
        if out:
            seen = set()
            for raw_line in out.split('\n'):
                raw_line = raw_line.strip()
                if not raw_line or raw_line.startswith('Refreshing'):
                    continue
                last_part = raw_line.split('\r')[-1].strip()
                if last_part and '.' in last_part:
                    pkg_name = last_part.rsplit('.', 1)[0]
                    if pkg_name not in seen:
                        seen.add(pkg_name)
                        upgrades.append({
                            'name': pkg_name,
                            'new_version': 'latest',
                            'source': 'tdnf',
                        })
        return upgrades


class DNF(BaseMgr):
    CLI = 'dnf'

    def __init__(self, module):
        super(DNF, self).__init__(module)
        self.explicit_pkgs = set()

    def _load_history(self):
        # Query dnf history list to get transaction IDs
        rc, out, err = self.module.run_command(['dnf', 'history', 'list'], handle_exceptions=False)
        if rc == 0 and out:
            ids = []
            for line in out.splitlines()[2:]:
                parts = line.split('|')
                if len(parts) >= 4:
                    tid = parts[0].strip()
                    if tid.isdigit():
                        ids.append(tid)

            if ids:
                rc_info, out_info, _ = self.module.run_command(['dnf', 'history', 'info'] + ids, handle_exceptions=False)
                if rc_info == 0 and out_info:
                    installed = set()
                    for line in out_info.splitlines():
                        if line.startswith('Command Line'):
                            cmd = line.split(':', 1)[1].strip()
                            parts = cmd.split()
                            if 'install' in parts:
                                idx = parts.index('install')
                                for p in parts[idx + 1:]:
                                    if not p.startswith('-') and '=' not in p and not p.endswith('.rpm'):
                                        installed.add(p)
                            if 'remove' in parts or 'erase' in parts:
                                act = 'remove' if 'remove' in parts else 'erase'
                                idx = parts.index(act)
                                for p in parts[idx + 1:]:
                                    if not p.startswith('-'):
                                        installed.discard(p)
                    self.explicit_pkgs = installed

    def list_installed(self):
        self._load_history()
        rc, out, err = self.module.run_command(
            ['rpm', '-qa', '--qf', '%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\t%{GROUP}\t%{SUMMARY}\n'],
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            raise Exception("Unable to list rpm packages rc=%s : %s" % (rc, err))
        return out.strip().split('\n')

    def get_package_details(self, line):
        parts = line.split('\t')
        if len(parts) < 5:
            return None
        name, version, arch, group, summary = parts[0], parts[1], parts[2], parts[3], parts[4]

        is_explicit = name in self.explicit_pkgs or any(name.startswith(p) for p in self.explicit_pkgs)
        is_system = name in BASE_SYSTEM_PACKAGES

        return {
            'name': name,
            'version': version,
            'arch': arch,
            'category': group if group != '(none)' else '',
            'description': summary if summary != '(none)' else '',
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'dnf',
        }

    def get_upgrades(self):
        upgrades = []
        rc, out, _ = self.module.run_command(['dnf', 'check-update', '-q'], handle_exceptions=False)
        if out:
            for line in out.splitlines():
                line = line.strip()
                if not line or line.startswith('Security:') or line.startswith('Last metadata'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    raw_name = parts[0]
                    pkg_name = raw_name.rsplit('.', 1)[0]
                    new_ver = parts[1]
                    upgrades.append({
                        'name': pkg_name,
                        'new_version': new_ver,
                        'source': 'dnf',
                    })
        return upgrades


class RPM(BaseMgr):
    CLI = 'rpm'

    def list_installed(self):
        rc, out, err = self.module.run_command(
            ['rpm', '-qa', '--qf', '%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\t%{GROUP}\t%{SUMMARY}\n'],
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            raise Exception("Unable to list rpm packages rc=%s : %s" % (rc, err))
        return out.strip().split('\n')

    def get_package_details(self, line):
        parts = line.split('\t')
        if len(parts) < 5:
            return None
        name, version, arch, group, summary = parts[0], parts[1], parts[2], parts[3], parts[4]
        is_system = name in BASE_SYSTEM_PACKAGES
        return {
            'name': name,
            'version': version,
            'arch': arch,
            'category': group if group != '(none)' else '',
            'description': summary if summary != '(none)' else '',
            'automatic': False,
            'install_reason': 'unknown',
            'system': is_system,
            'source': 'rpm',
        }


class APT(BaseMgr):
    CLI = 'dpkg-query'

    def __init__(self, module):
        super(APT, self).__init__(module)
        self.manual_pkgs = set()

    def _load_manual(self):
        apt_mark = shutil.which('apt-mark')
        if apt_mark:
            rc, out, _ = self.module.run_command([apt_mark, 'showmanual'], handle_exceptions=False)
            if rc == 0 and out:
                self.manual_pkgs = set(out.strip().splitlines())

    def list_installed(self):
        self._load_manual()
        rc, out, err = self.module.run_command(
            [self._cli, '-W', '-f=${Package}\t${Version}\t${Architecture}\t${Section}\t${Priority}\t${binary:Summary}\t${db:Status-Status}\n'],
            handle_exceptions=False,
        )
        if rc != 0 or not out:
            raise Exception("Unable to list dpkg packages rc=%s : %s" % (rc, err))
        lines = []
        for line in out.strip().splitlines():
            parts = line.split('\t')
            if len(parts) >= 7 and parts[6] == 'installed':
                lines.append(line)
        return lines

    def get_package_details(self, line):
        parts = line.split('\t')
        if len(parts) < 6:
            return None
        name, version, arch, section, priority, summary = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        is_explicit = (name in self.manual_pkgs) if self.manual_pkgs else (priority not in ('required', 'important'))
        is_system = name in BASE_SYSTEM_PACKAGES or priority in ('required', 'important') or section in ('base', 'admin', 'kernel')
        return {
            'name': name,
            'version': version,
            'arch': arch,
            'category': section,
            'description': summary,
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'apt',
        }

    def get_upgrades(self):
        upgrades = []
        apt_get = shutil.which('apt-get')
        if apt_get:
            rc, out, _ = self.module.run_command([apt_get, '-s', 'upgrade'], handle_exceptions=False)
            if rc == 0 and out:
                for line in out.splitlines():
                    m = re.match(r"^Inst\s+(\S+)\s+\[(\S+)\]\s+\((\S+)", line.strip())
                    if m:
                        upgrades.append({
                            'name': m.group(1),
                            'current_version': m.group(2),
                            'new_version': m.group(3),
                            'source': 'apt',
                        })
        return upgrades


class APK(BaseMgr):
    CLI = 'apk'

    def __init__(self, module):
        super(APK, self).__init__(module)
        self.world_pkgs = set()

    def _load_world(self):
        try:
            with open('/etc/apk/world', 'r') as f:
                for line in f:
                    pkg = line.strip()
                    if pkg:
                        pkg = re.split(r'[<>=~]', pkg)[0]
                        self.world_pkgs.add(pkg)
        except Exception:
            pass

    def list_installed(self):
        self._load_world()
        rc, out, err = self.module.run_command([self._cli, 'info', '-v'], handle_exceptions=False)
        if rc != 0 or not out:
            raise Exception("Unable to list apk packages rc=%s : %s" % (rc, err))
        return [l.strip() for l in out.strip().splitlines() if l.strip()]

    def get_package_details(self, line):
        m = re.match(r"^(.+)-([0-9][^-]*-r[0-9]+)$", line)
        if m:
            name, version = m.group(1), m.group(2)
        else:
            parts = line.rsplit('-', 2)
            name = parts[0]
            version = '-'.join(parts[1:]) if len(parts) > 1 else ''
        if not name:
            return None
        is_explicit = (name in self.world_pkgs) if self.world_pkgs else True
        is_system = name in BASE_SYSTEM_PACKAGES or name in ('alpine-baselayout', 'alpine-keys', 'apk-tools', 'busybox', 'musl', 'musl-utils')
        return {
            'name': name,
            'version': version,
            'arch': '',
            'category': '',
            'description': '',
            'automatic': not is_explicit,
            'install_reason': 'explicit' if is_explicit else 'dependency',
            'system': is_system,
            'source': 'apk',
        }

    def get_upgrades(self):
        upgrades = []
        rc, out, _ = self.module.run_command([self._cli, 'version', '-l', '<'], handle_exceptions=False)
        if rc == 0 and out:
            for line in out.strip().splitlines():
                line = line.strip()
                if not line or line.startswith('Installed:'):
                    continue
                m = re.match(r"^(.+)-([0-9][^-]*-r[0-9]+)\s+<\s+(\S+)", line)
                if m:
                    upgrades.append({
                        'name': m.group(1),
                        'current_version': m.group(2),
                        'new_version': m.group(3),
                        'source': 'apk',
                    })
        return upgrades


MANAGERS = {
    'pacman': PACMAN,
    'yay': YAY,
    'pkg': PKG,
    'tdnf': TDNF,
    'dnf': DNF,
    'apt': APT,
    'apk': APK,
    'rpm': RPM,
}

PRIORITY_ORDER = ['pacman', 'pkg', 'tdnf', 'dnf', 'apt', 'apk', 'rpm', 'yay']


def main():
    module = AnsibleModule(
        argument_spec=dict(
            manager=dict(type='list', elements='str', default=['auto']),
            strategy=dict(choices=['first', 'all'], default='first'),
            filter_dependencies=dict(type='bool', default=False),
            filter_system=dict(type='bool', default=False),
            check_upgrades=dict(type='bool', default=False),
        ),
        supports_check_mode=True,
    )

    req_managers = [m.lower() for m in module.params['manager']]
    strategy = module.params['strategy']
    filter_deps = module.params['filter_dependencies']
    filter_sys = module.params['filter_system']
    check_upg = module.params['check_upgrades']

    if 'auto' in req_managers:
        search_list = PRIORITY_ORDER
    else:
        search_list = req_managers

    all_packages = {}
    found_mgrs = []

    for mgr_name in search_list:
        if mgr_name not in MANAGERS:
            continue

        mgr_cls = MANAGERS[mgr_name]
        mgr_instance = mgr_cls(module)

        if mgr_instance.is_available():
            try:
                pkgs = mgr_instance.get_packages()
                if pkgs:
                    found_mgrs.append(mgr_name)
                    for k, v in pkgs.items():
                        if k not in all_packages:
                            all_packages[k] = v
                        else:
                            all_packages[k].extend(v)

                    if strategy == 'first':
                        break
            except Exception as e:
                module.warn("Package manager %s failed: %s" % (mgr_name, to_text(e)))

    if not found_mgrs:
        module.fail_json(msg="No supported package manager found on this host.")

    # Check for available upgrades if requested
    upgradeable_packages = []
    if check_upg and found_mgrs:
        primary_mgr = found_mgrs[0]
        try:
            mgr_inst = MANAGERS[primary_mgr](module)
            if mgr_inst.is_available():
                upgradeable_packages = mgr_inst.get_upgrades()
        except Exception as e:
            module.warn("Failed to check upgrades with %s: %s" % (primary_mgr, to_text(e)))

    # Filter packages if requested
    filtered_packages = {}
    explicit_packages_list = []

    for name, versions in all_packages.items():
        surviving_versions = []
        for v in versions:
            is_auto = v.get('automatic', False)
            is_sys = v.get('system', False)

            if not is_auto and not is_sys:
                explicit_packages_list.append(v)

            if filter_deps and is_auto:
                continue
            if filter_sys and is_sys:
                continue
            surviving_versions.append(v)

        if surviving_versions:
            filtered_packages[name] = surviving_versions

    # Sort explicit packages list alphabetically by name
    explicit_packages_list.sort(key=lambda x: x.get('name', '').lower())

    results = {
        'ansible_facts': {
            'packages': filtered_packages,
            'explicit_packages': explicit_packages_list,
            'explicit_packages_count': len(explicit_packages_list),
            'package_manager_detected': found_mgrs[0] if found_mgrs else 'none',
            'upgradeable_packages': upgradeable_packages,
            'upgradeable_packages_count': len(upgradeable_packages),
        },
        'explicit_packages_count': len(explicit_packages_list),
        'package_manager': found_mgrs[0] if found_mgrs else 'none',
        'upgradeable_packages': upgradeable_packages,
        'upgradeable_packages_count': len(upgradeable_packages),
        'changed': False,
    }

    module.exit_json(**results)


if __name__ == '__main__':
    main()
