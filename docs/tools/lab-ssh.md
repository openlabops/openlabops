# lab-ssh 叢集金鑰管理與輪換套件說明文件

[`bin/lab-ssh`](../../tools/bin/lab-ssh)（實作：[`lib/lab_ssh.py`](../../tools/lib/lab_ssh.py)）（系統指令：`lab-ssh`）為 OpenLabOps 全網伺服器金鑰輪換、端點金鑰生成 (WSL 自動辨識)、公鑰全網抹除與客戶端連線組態同步之專業套件。

---

## 雙重調用行為規範 (Invocation Behaviors)

1. **從總控制台 `lab-tools` 選取時**：
   - **預設行為**：**一鍵依序輪換全網所有伺服器 SSH 金鑰**（Lab Master ➔ OpenLabOps/Virtualization ➔ Git OpenLabOps），完成多階段派發、Secrets 提交與目標節點自動部署。
   - **選單進入**：亦可選取進入微調選單，進行個別金鑰維護。
2. **獨立執行 `lab-ssh` 時**：
   - 開啟 TUI 選單儀表板，支援單項金鑰輪換、本地端點金鑰生成、清除抹除 (Revoke) 與客戶端同步。

---

## 功能特性

- **三階段金鑰輪換**：
  - `rotate-ansible-keys.yml`：Ansible 納管 Master 連線金鑰（相容別名: `rotate-lab-keys.yml`）。
  - `rotate-openlab-keys.yml`：7/24 伺服器與 Virtualization 底層虛擬機金鑰 (`ansible.key`)。
  - `rotate-git-openlab-keys.yml`：Gitea API 與 GitHub API 雙向註冊，並自動完成雙端 SSH 驗證。
- **WSL 內核自動識別**：
  - 本地生成端點金鑰時，若檢測為 WSL 內核且名稱未帶 wsl，自動標記命名為 `<hostname>_wsl`，支援 Passphrase 密碼保護。
- **免密明文模式相容**：
  - 模式 `0600` 免密 `.gitea_token`，完全無提示阻斷與警告雜訊。

---

## 常用 CLI 命令

| 指令 | 說明 |
| :--- | :--- |
| `lab-ssh` | 啟動 TUI 專業金鑰選單 |
| `lab-ssh -a` / `--rotate-all` | **[預設一鍵]** 依序輪換所有伺服器 SSH 金鑰 |
| `lab-ssh --rotate-lab` | 派發 Lab SSH 金鑰輪換 |
| `lab-ssh --rotate-openlab` | 派發 OpenLabOps & Virtualization SSH 金鑰輪換 |
| `lab-ssh --rotate-git` | 派發 Git OpenLabOps SSH 金鑰輪換 |
| `lab-ssh -g` / `--gen-key [host]` | 產生端點本機 SSH 金鑰對 (WSL 自動辨識) 並部署至伺服器 |
| `lab-ssh --sync-keys` | 同步受控 SSH 管理私鑰與公鑰 (~/.ssh/*.key) |
| `lab-ssh --sync-config` | 同步本機標準 ~/.ssh/config 連線別名 |
| `lab-ssh --revoke <host>` | 定點清除特定端點公鑰並自 secrets 抹除 |
| `lab-ssh -t <target_node>` | 指定金鑰輪換後自動部署私鑰之目標端點 (預設: `control-node`) |
