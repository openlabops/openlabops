---
id: lab-status-and-ssh
title: "叢集健康與 SSH 生命週期"
sidebar_position: 5
---

# 叢集健康與 SSH 生命週期 CLI

位於 `tools/bin/`，100% 零外部依賴（`[INV-01]`），遠端 Ansible 任務透過 `tools/lib/core/gitea_api.py` 派發至 Gitea Actions。

## `lab-status`

**引擎：** `tools/lib/lab_status.py`

```bash
lab-status [-q] [-k] [-a] [-n] [-d] [-p HOST] [-b | -t] [--json]
```

* `-q` 僅測本機、`-k` 僅檢金鑰、`-a` 稽核 `authorized_keys` 異常公鑰、`-n` 僅看節點、`-p HOST` 單機診斷（搭配 `-d` 顯示完整 STDERR）。

## `lab-ssh`

**引擎：** `tools/lib/lab_ssh.py`

```bash
lab-ssh [-a | --rotate-all] [--rotate-ansible] [--rotate-storage] [--rotate-git]
        [-t TARGET] [-g [HOSTNAME]] [--sync-keys] [--sync-config] [--revoke HOSTNAME]
```

* 派發三階段零中斷金鑰輪替、生成端點金鑰（`-g`）、同步 `~/.ssh/config`（`--sync-config`）或撤銷端點公鑰（`--revoke`）。

## `lab-boot-sync`

**引擎：** `tools/lib/lab_boot_sync.py` & `tools/lib/core/lockout.py`

```bash
lab-boot-sync [-c | --check] [-f | --force] [-w | --wait] [--timeout SEC]
              [--target-host HOST] [--target-user USER]
```

* 比對本機 `/etc/<prefix>/last_synced_commit` 與遠端 `<prefix>-secrets` HEAD SHA；若過期則派發 `deploy-ssh-keys.yml`（`source_commit_sha`、`deploy_client_keys=false`）補推公鑰並寫入 `/run/<prefix>/synced_ok` 解除鎖定。
