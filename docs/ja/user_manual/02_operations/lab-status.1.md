# lab-STATUS(1) - Cluster Status Dashboard & Zero-Trust Key Audit

## NAME
`lab-status` - Fleetwide Server Status Dashboard & Live Telemetry Inspector

## カテゴリ (CATEGORY)
> **[日常運用アプリ (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-status [OPTIONS]
```

## DESCRIPTION
`lab-status` queries live cluster status across all managed servers, storage appliances, and hypervisors.
It inspects:
1. Online status and latency via SSH handshake.
2. System load, CPU cores, memory utilization, and disk mounts.
3. Active Docker containers and ports.
4. **Zero-Trust Key Audit (`-k`)**: Inspects every line in `/home/<user>/.ssh/authorized_keys` across all nodes, comparing key fingerprints against known site keys (`ansible.key`, `id_user.key`, `git.key`) to detect rogue backdoor keys or altered `from="..."` IP restrictions.

## OPTIONS
- `-k, --keys`       : Enable deep zero-trust authorized_keys audit.
- `-a, --all`        : Query all nodes (including offline appliances and endpoints).
- `-j, --json`       : Output machine-readable JSON telemetry.
- `-q, --quiet`      : Minimal output mode.
- `-v, --verbose`    : Detailed debugging logs.

## EXAMPLES
```bash
# Standard dashboard:
lab-status

# Zero-trust authorized_keys audit:
lab-status -k

# Export telemetry to JSON:
lab-status --json > telemetry.json
```

