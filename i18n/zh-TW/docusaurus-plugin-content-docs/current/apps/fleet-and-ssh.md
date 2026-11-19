---
id: fleet-and-ssh
title: 集群維運與 SSH 生命週期
sidebar_position: 2
---

# 集群維運與 SSH 生命週期 CLI

位於 `tools/bin/` 目錄下，100% 零外部 Python 依賴（`[INV-01]`）。所有需要執行 Ansible 劇本的操作皆透過 `tools/lib/core/gitea_api.py` 派發至遠端 Gitea Actions。

---

## `lab-status`

**底層引擎：** `tools/lib/lab_status.py`

即時集群健康儀表板、SSH 金鑰監控與 `authorized_keys` 後門稽核工具。

```bash
lab-status [-q] [-k] [-a] [-n] [-d] [-p HOST] [-b | -t] [--json]
```

* `-q, --quick`：僅探測本機，略過遠端節點。
* `-k, --keys-only`：僅顯示受控 SSH 私鑰與 Agent 狀態。
* `-a, --audit-keys`：深入掃描所有節點 `authorized_keys`，比對合法指紋並揪出未受控公鑰。
* `-n, --nodes-only`：僅顯示伺服器節點與套件狀態。
* `-p, --probe HOST`：針對單一節點執行深度診斷（搭配 `-d` 顯示 STDERR 與 Exit Code）。
* `-b` / `-t` / `--json`：切換彩色卡片 UI、極簡表格（預設）或結構化 JSON 輸出。

---

## `lab-ssh`

**底層引擎：** `tools/lib/lab_ssh.py`

SSH 金鑰生命週期管理與三階段輪替派發器。

```bash
lab-ssh [-a | --rotate-all] [--rotate-ansible] [--rotate-storage] [--rotate-git]
        [-t TARGET] [-g [HOSTNAME]] [--sync-keys] [--sync-config] [--revoke REVOKE]
```

* `--rotate-ansible` / `--rotate-git` / `--rotate-all`：派發 Gitea Actions 劇本執行三階段零停機金鑰輪替。
* `-g [HOSTNAME]`：產生本機端點金鑰並部署公鑰至伺服器群。
* `--sync-keys` / `--sync-config`：同步受控金鑰與標準 `~/.ssh/config` 主機別名。
* `--revoke HOSTNAME`：全網撤銷指定已除役端點之 SSH 公鑰。

---

## `lab-setup`

**底層引擎：** `tools/lib/lab_setup.py`

伺服器預備與 Setup Trigger 步驟派發器。

```bash
lab-setup [-l | --list] [-p | --provision] [-t TARGET] [-a | --all] [-s STEP] [-m {gitea,local}]
```

* 列出或執行已註冊之初始化步驟（如 `system_base_provisioning`、`pull_docker_compose`），預設經由 Gitea Actions 派發（`-m gitea`），亦支援本機模式（`-m local`）。

---

## `lab-upgrade`

**底層引擎：** `tools/lib/lab_upgrade.py`

多發行版 Linux 套件升級儀表板。

```bash
lab-upgrade [-s | --serial] [-f | --force] [hosts ...]
```

* 自動篩選有待升級套件的節點（或指定主機），預設以平行儀表板執行，加上 `-s` 則改為循序串流輸出日誌。

---

## `lab-tools`

**底層引擎：** `tools/lib/lab_tools.py`

頂層 Curses TUI 維運控制台（`tools/lib/core/ui_curses.py`），整合狀態監控、金鑰輪替、Gitea Actions 執行紀錄診斷（`inspect-run <ID>`）與端點撤銷。傳入 `--plain` / `--no-tui` 可切換為純文字模式。

---

## `lab-boot-sync`

**底層引擎：** `tools/lib/lab_boot_sync.py`

端點開機公鑰同步器與鎖定防護（Lockout Guard）。

```bash
lab-boot-sync [-c | --check] [-f | --force] [-w | --wait] [--timeout SEC]
              [--target-host HOST] [--target-user USER]
```

* 比對本機狀態與遠端 `openlab-secrets` 最新 Commit SHA；若不同步則觸發金鑰部署並等待收斂（`-w`），通過後寫入 `/run/openlab/synced_ok` 解鎖端點環境。
