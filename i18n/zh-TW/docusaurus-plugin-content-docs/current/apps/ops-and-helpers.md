---
id: ops-and-helpers
title: 配置同步、備份與輔助工具
sidebar_position: 3
---

# 配置同步、備份與輔助工具 CLI

---

## `lab-backup`

**底層引擎：** `tools/lib/lab_backup.py`

集群備份與共享配置廣播套件。

```bash
lab-backup [-a | --all] [-g | --gateway] [-b | --broadcast] [-s SOURCE]
```

* `-g, --gateway`：備份閘道器防火牆與 DNS 設定。
* `-b, --broadcast`：自 `-s SOURCE` 收集共享本機配置並廣播同步至全網。
* `-a, --all`：同時執行閘道器備份與共享配置廣播。

---

## `lab-config`

**底層引擎：** `tools/lib/lab_config.py`

雙向 GitOps 本機配置控制器（`/usr/local/etc` / `backup.yml`）。

```bash
lab-config [--init | --show | --diff | --update | --reset | --restore] [-m MESSAGE]
```

* `--init`：從遠端範本初始化本機設定。
* `--show` / `--diff`：檢視本機設定或比對遠端倉庫 HEAD 差異。
* `--update`：驗證並推送本機修改至倉庫，觸發全網同步。
* `--reset` / `--restore`：放棄本機修改覆寫為遠端 HEAD，或還原至上一版（`HEAD~1`）。

---

## `lab-info`

**底層引擎：** `tools/lib/lab_info.py`

CMDB 硬體與套件遙測套件。

```bash
lab-info [-a | --all] [-d | --dispatch-only] [-p | --pull-only] [-r | --render-only]
```

* 派發 Gitea Actions 稽核工作流（`-d`）、拉取更新後的 `openlab-configs`（`-p`），並將 `node-information/node_*.json` 渲染為 Markdown 節點手冊（`-r`）。

---

## `lab-man`

**腳本：** `tools/bin/lab-man`（`bin/lab-man` 軟連結）

內建終端機指令手冊瀏覽器（例如 `lab-man status`、`lab-man init`）。

---

## 獨立輔助腳本 (`tools/bin/`)

| 腳本 | 底層引擎 | 用途 |
| :--- | :--- | :--- |
| **`sync-ops-tools`** | `tools/lib/sync_ops_tools.py` | 檢查版本並部署/升級遠端節點之 `openlabops` CLI 工具鏈（`-c`、`-f`、`-l`）。 |
| **`sync-ssh-config`** | `tools/lib/sync_ssh_config.py` | 渲染並同步標準 `~/.ssh/config` 主機別名（`-p openlab \| endpoint`）。 |
| **`sync-ssh-keys`** | `tools/lib/sync_ssh_keys.py` | 透過 Gitea Runner 部署受控 SSH 金鑰並修正檔案權限（`-n`、`-u`、`-k`）。 |
| **`generate-host-ssh-key`** | `tools/lib/generate_host_ssh_key.py` | 為端點主機產生專屬 Ed25519 金鑰對（`-H HOSTNAME`）並派發部署公鑰。 |
| **`revoke-host-ssh-key`** | `tools/lib/revoke_host_ssh_key.py` | 全網撤銷指定端點主機之 SSH 公鑰（`-H HOSTNAME`、`--keep-secrets`、`-l`、`-y`）。 |
| **`render-node-doc`** | `tools/lib/render_node_doc.py` | 將 `node_*.json` CMDB 遙測檔渲染為人類可讀之 Markdown 手冊（`-o` / `-d`）。 |
