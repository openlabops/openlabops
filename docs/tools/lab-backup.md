# lab-backup 叢集備份與共用組態廣播套件說明文件

[`bin/lab-backup`](../../tools/bin/lab-backup)（實作：[`lib/lab_backup.py`](../../tools/lib/lab_backup.py)）（系統指令：`lab-backup`）為 OpenLabOps 全網 Gateway 防火牆/DNS 備份、以及本機組態採集與共用家族變更全網廣播 (**Console Shared Config Broadcast / Family Deploy**) 之專業套件。

---

## 核心功能特色

### 1. Console Family Change Deploy (共用組態採集與廣播)
- 當你在當前管理機修改了共用設定（如 `openlab.*`、`.vimrc`、`nvim/`、`tmux.conf` 等）：
  - 觸發 `sync-node-config.yml` 進行組態採集。
  - Gitea Runner 比對 Diff，**自動透過 Ansible 將共用組態廣播更新至全網其他所有節點**！
  - 若僅為該主機之特有組態（如 `<hostname>.*`），則僅於 `openlab-configs` 完成雲端備份，不推播至其他機器。

### 2. Gateway 防火牆與 DNS 備份
- 派發 `backup-gateway-config.yml`：
  - 備份 pfSense / OPNsense / Gateway 之 `pf.conf` 防火牆過濾規則。
  - 備份 Unbound DNS 本地解析組態。

---

## 雙重調用行為規範 (Invocation Behaviors)

1. **從總控制台 `lab-tools` 選取時**：
   - **預設行為**：**一鍵全套備份**（依序執行 閘道備份與本機共用組態採集廣播）。
   - **選單進入**：亦可選取進入微調選單，單獨執行特定備份。
2. **獨立執行 `lab-backup` 時**：
   - 開啟 TUI 選單儀表板，支援個別執行或一鍵全套備份。

---

## 常用 CLI 命令

| 指令 | 說明 |
| :--- | :--- |
| `lab-backup` | 啟動 TUI 備份選單 |
| `lab-backup -a` / `--all` | **[預設一鍵]** 依序執行閘道備份與本機共用組態廣播 |
| `lab-backup -b` / `--broadcast` | 採集本機組態並廣播共用家族變更至全網 (Family Deploy) |
| `lab-backup -g` / `--gateway` | 僅備份 Gateway 防火牆與 DNS 組態 |
| `lab-backup -s <source_host>` | 指定組態採集之來源主機 (預設為當前主機) |
