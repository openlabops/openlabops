# lab-SETUP(1) - Server Base Setup & Docker Compose Provisioning

## NAME
`lab-setup` - Fleetwide Server Base Provisioning & Container Hook Setup Tool

## CATEGORY
> **[Post-Installation Operational App]**

## SYNOPSIS
```bash
lab-setup [OPTIONS]
```

## DESCRIPTION
`lab-setup` provides an interactive TUI dashboard and CLI runner to execute modular server provisioning steps across managed nodes:
1. SSH config and key distribution synchronization.
2. Base operating system configuration (timezone, locale, core packages).
3. Docker Compose repositories synchronization and post-push hooks.
4. SSH key rotations and hardening.

## OPTIONS
- `-p, --provision`   : Execute standard base provisioning and container setup on servers.
- `-l, --list`        : List all registered setup steps and statuses.
- `-s, --step <ID>`   : Execute a single specific step by identifier.
- `-a, --all`         : Run all enabled trigger steps sequentially.
- `-t, --target <GRP>`: Specify target host group (default: `servers`).
- `-m, --mode <MODE>` : Execution mode (`remote` via Gitea Actions or `local` Ansible).

## EXAMPLES
```bash
# Launch interactive TUI setup dashboard:
lab-setup

# Run default one-click server provisioning:
lab-setup -p

# Execute a single setup step:
lab-setup -s pull_docker_compose
```

