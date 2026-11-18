# lab-SSH(1) - SSH Dispatcher & Key Lifecycle Controller

## NAME
`lab-ssh` - Intelligent Interactive SSH Connection Terminal & Key Rotation

## 類別 (CATEGORY)
> **[日常運維 App (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-ssh [OPTIONS] [TARGET_NODE]
```

## DESCRIPTION
`lab-ssh` manages SSH connections, client configuration synchronization, endpoint key issuance, and 4-phase zero-downtime key rotation.
When called with a target hostname, it looks up the node in CMDB and opens an interactive SSH session using the proper identity key profile.

## OPTIONS
- `-t, --target <NODE>`       : Target host to connect to.
- `-g, --gen-key [NAME]`      : Generate new client/endpoint key pair dynamically.
- `--revoke <FINGERPRINT>`    : Revoke authorized key from target nodes.
- `--sync-keys`               : Sync public keys from secrets repository to nodes.
- `--sync-config`             : Re-render and distribute `~/.ssh/config` client aliases.
- `--rotate-ansible`          : Execute 4-phase zero-downtime Ansible key rotation.
- `--rotate-storage`          : Execute storage appliance key rotation.
- `--rotate-git`              : Execute version control Gitea Git key rotation.

## KEY ROTATION PHASES (ZERO DOWNTIME)
1. **Stage 1 (Add)**: Appends new public key to target `authorized_keys`.
2. **Stage 2 (Verify)**: Verifies successful authentication with new private key.
3. **Stage 3 (Remove)**: Removes old public key from target `authorized_keys`.
4. **Stage 4 (Purge)**: Purges old local key and commits updated fingerprint to CMDB.

## EXAMPLES
```bash
# Connect to node 'base':
lab-ssh base

# Execute Ansible key rotation across cluster:
lab-ssh --rotate-ansible

# Synchronize SSH client aliases:
lab-ssh --sync-config
```

