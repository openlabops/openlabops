# lab-BACKUP(1) - Declarative Bi-directional Backup Suite

## NAME
`lab-backup` - Declarative Node Configuration Archiving & Recovery

## 類別 (CATEGORY)
> **[日常運維 App (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-backup [OPTIONS]
```

## DESCRIPTION
`lab-backup` drives the unified bi-directional file synchronization engine:
- **Upstream Backup (`backup-node.yml`)**: Fetches remote node files into `openlab-configs/<hostname>/` based on the host's declarative `backup: [{src, dest}]` list.
- **Downstream Restore (`restore-node.yml`)**: Restores configuration and dotfiles back to target nodes with exact permissions (`mode`, `owner`, `group`).

## OPTIONS
- `-a, --all`          : Run backup against all managed cluster hosts.
- `-t, --target <NODE>` : Run backup against a specific node.
- `-r, --restore`      : Run restore playbook to deploy files back to node.
- `-b, --backup`       : Run backup playbook (default).
- `-s, --source <PATH>` : Override destination path in configs repository.

## DECLARATIVE VARIABLE STRUCTURE
Backup targets are defined in `conf/backup.yml` (or `/usr/local/etc/{cluster}/conf/backup.yml`):
```yaml
backup:
  - src: "/etc/resolv.conf"
    dest: "network/resolv.conf"
  - src: "/etc/nginx/nginx.conf"
    dest: "nginx/nginx.conf"
    mode: "0644"
```

## EXAMPLES
```bash
# Backup all nodes:
lab-backup -a

# Backup single node 'gateway':
lab-backup -t gateway

# Restore files to node 'srv-node1':
lab-backup -t srv-node1 --restore
```

