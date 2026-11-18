# lab-NODE(1) - Node Onboarding & Dynamic Telemetry Tool

## NAME
`lab-node` - Dynamic Node Onboarding, Live Fact Scouting & Key Handover

## CATEGORY
> **[Installation & Initial Setup]**

## SYNOPSIS
```bash
./bin/lab-node add [OPTIONS] <TARGET_IP>
./bin/lab-node remove [-f|--force] [--purge] [--no-revoke] <HOSTNAME_OR_IP>
./bin/lab-node list
./bin/lab-node sync [TARGET_IP]
```

## DESCRIPTION
`lab-node` provides single-node onboarding and full lifecycle management.
- `add`: Logs into target machine via password or SSH key, uploads `bootstrap_probe.sh`, executes real-time probing, outputs ground truth facts (`conf/nodes/<hostname>.json`), performs key injection, and triggers dynamic classification.
- `remove`: Decommissions and unmanages a node from the cluster. Connects to the remote node to revoke the management key from `~/.ssh/authorized_keys`, removes facts from active CMDB and `conf/nodes/` (with archive or purge options), and re-compiles `ansible/inventory/hosts.yml` and `current.json`.
- `list`: Reads all `conf/nodes/*.json` files and prints a rich status table showing hostname, primary IP, category, OS/Firmware, CPU cores, RAM, and Docker status.
- `sync`: Re-probes target node facts and updates `conf/nodes/<hostname>.json`.

## OPTIONS
- `-u, --user <USERNAME>` : Initial SSH user (default: `labadmin` or `root`).
- `-p, --password <PASS>` : Initial SSH password (prompted securely if omitted).
- `-t, --target-user <USER>`: Permanent automation user to provision (default: `lab`).
- `-k, --key <PATH>`      : SSH private key for authentication.
- `--purge`               : Purge all facts and backups for target node instead of archiving.
- `--no-revoke`           : Skip revoking management key from remote authorized_keys.
- `-f, --force`           : Force decommission without interactive prompts.
- `--no-interactive`     : Run without interactive prompts.

## EXAMPLES
```bash
# Add new node interactively:
./bin/lab-node add 192.168.1.230

# List all ingested cluster nodes:
./bin/lab-node list
```

