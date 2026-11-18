# lab-DISCOVER(1) - Dynamic Node Telemetry Inspector

## NAME
`lab-discover` - Machine Telemetry Fact Harvester & Zero-Trust Key Auditor

## CATEGORY
> **[Development, Testing & IaC]**

## SYNOPSIS
```bash
./bin/lab-discover [OPTIONS]
```

## DESCRIPTION
`lab-discover` connects to remote managed nodes via OpenSSH to audit hardware specs (CPU, RAM, Disks, Network interfaces), active Docker containers, and live `authorized_keys`. The gathered facts are written to pure JSON files in `node-information/node_<hostname>.json` or `conf/nodes/<hostname>.json` without modifying remote systems.

## OPTIONS
- `--node <HOSTNAME>` : Audit only a single specified node.
- `--all`             : Audit all nodes declared in the cluster manifest.
- `--help, -h`        : Display usage summary.

## EXAMPLES
```bash
# Discover live telemetry for a single node:
./bin/lab-discover --node lab

# Discover all declared cluster nodes:
./bin/lab-discover --all
```

