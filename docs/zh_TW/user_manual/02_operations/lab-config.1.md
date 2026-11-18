# lab-CONFIG(1) - Local Config & GitOps Sync Controller

## NAME
`lab-config` - Local Declarative Configuration Manager & GitOps Sync

## 類別 (CATEGORY)
> **[日常運維 App (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-config [OPTIONS]
```

## DESCRIPTION
`lab-config` bridges the gap between local configuration files (`/usr/local/etc/{cluster}/conf/backup.yml` or `~/.config/{cluster}/backup.yml`) and the central Gitea configuration repository (`openlab-configs`).
It allows operators to edit declarative YAML files locally, validate syntax without third-party dependencies, display unified diffs against Gitea HEAD, push changes, and rollback.

## OPTIONS
- `--init`                 : Initialize local `/usr/local/etc` config from remote template.
- `--show`                 : Print current local configuration to stdout.
- `--diff`                 : Display unified diff between local file and remote Gitea repository.
- `--update`               : Validate YAML and push changes to Gitea repository.
- `--reset`                : Discard uncommitted local edits and overwrite from remote HEAD.
- `--restore`              : Rollback local file to previous commit (HEAD~1).
- `-m, --message <MSG>`    : Custom commit message for `--update`.
- `--cluster <NAME>`       : Cluster identifier (default: `openlab`).
- `--config-path <PATH>`   : Explicit override path to local config file.

## EXAMPLES
```bash
# Initialize local backup.yml:
lab-config --init

# Compare local changes against central repository:
lab-config --diff

# Validate and push changes to Gitea:
lab-config --update -m "feat(backup): add postgresql configuration backup"

# Discard local edits:
lab-config --reset
```

