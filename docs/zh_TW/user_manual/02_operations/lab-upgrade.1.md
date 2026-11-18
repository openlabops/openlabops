# lab-UPGRADE(1) - Multi-Node Concurrent Package Maintenance

## NAME
`lab-upgrade` - Multi-Node Concurrent Package Maintenance & Patching

## 類別 (CATEGORY)
> **[日常運維 App (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-upgrade [OPTIONS] [HOSTS...]
```

## DESCRIPTION
`lab-upgrade` checks and installs updates across multiple operating system families concurrently (Arch Linux, Debian/Ubuntu, RHEL/Oracle, Photon OS) using their native package managers (`pacman`, `apt`, `dnf`, `tdnf`, `pkg`).

## OPTIONS
- `-s, --check`      : Dry-run check for available package updates without applying.
- `-f, --force`      : Proceed without interactive confirmation.
- `-v, --verbose`    : Show detailed package manager execution logs.

## EXAMPLES
```bash
# Check for updates across all nodes:
lab-upgrade -s

# Upgrade specific node:
lab-upgrade base
```

