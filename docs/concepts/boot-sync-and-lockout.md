---
id: boot-sync-and-lockout
title: "Stale Key Auto-Sync & Lockout Guard"
sidebar_position: 4
---

# Boot-Time Stale Key Auto-Sync & Lockout Guard

Workstations, laptops, and intermittent nodes (`always_online: false`) may be powered off when a cluster-wide SSH key rotation occurs. When they boot back up, their `authorized_keys` contain expired/deprecated public keys.

OpenLabOps solves this without ever distributing private keys over HTTP (`[INV-02]`):

```mermaid
sequenceDiagram
    participant N as Intermittent Node
    participant G as Gitea (openlab-secrets & Actions)
    N->>G: Compare /etc/<prefix>/last_synced_commit vs secrets HEAD SHA
    alt SHA Matches (Fast Path)
        N->>N: Write /run/<prefix>/synced_ok (Unlock)
    else SHA Stale (Missed Rotation)
        N->>G: Dispatch deploy-ssh-keys.yml (source_commit_sha, deploy_client_keys=false)
        G->>N: Runner authenticates with historical key from source_commit_sha
        G->>N: Push latest public key, purge old key by comment, update last_synced_commit
        N->>N: Write /run/<prefix>/synced_ok (Unlock)
    end
```

## Mechanism Details

1. **Secrets Git SHA Index (`tools/lib/lab_boot_sync.py`)**:
   * Each node records `/etc/<prefix>/last_synced_commit`.
   * On boot (or `lab-boot-sync`), the node queries the remote `<prefix>-secrets` `HEAD` commit SHA via Gitea API.
2. **Fast Path vs. Roll-Forward Sync**:
   * **Identical SHA**: Keys are current; `/run/<prefix>/synced_ok` is created immediately.
   * **Stale SHA**: `lab-boot-sync` dispatches `deploy-ssh-keys.yml` with `target_hosts`, `source_commit_sha`, and `deploy_client_keys=false`. The Gitea Act Runner uses the historical key at `source_commit_sha` to log in, inject the latest public key, purge the expired key, and update `/etc/<prefix>/last_synced_commit`.
3. **Lockout Guard (`tools/lib/core/lockout.py`)**:
   * On intermittent nodes, `lab-*` automation commands remain locked until `/run/<prefix>/synced_ok` exists, preventing operations against out-of-sync credentials.
   * Always-online master consoles (`always_online: true`) bypass this lockout.
