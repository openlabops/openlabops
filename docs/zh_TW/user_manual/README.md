# OpenLabOps Operations Engine: Official User Manual
<!-- MACHINE-OPTIMIZED CONTEXT SPECIFICATION: MANDATORY REFERENCE -->

Welcome to the **OpenLabOps Operations Engine CLI Manual**.
All tools adhere strictly to **`[INV-01]` (Zero External Dependencies, 100% Python Standard Library)** and **`[INV-02]` (Zero Credentials in Repo)**.

本手冊文件依使用情境實體劃分於三個子目錄，亦可透過終端選單 `./bin/lab-man` 或 `./bin/lab-tools` 在螢幕上互動選取閱讀：

---

## 🚀 1. 安裝、引導與節點上架 ([`01_installation/`](01_installation))
> 用於 Day-0 初次建構叢集、建立本地 Gitea 五庫聯邦、實機硬體探測與動態節點上線。

| 指令 (CLI Command) | 概要說明 (Description) | 實體手冊路徑 (Manual File) |
| :--- | :--- | :--- |
| **`lab-init(1)`** | Day-0 叢集開箱初始化精靈 | [`01_installation/lab-init.1.md`](01_installation/lab-init.1.md) |
| **`lab-node(1)`** | 動態節點上架與配置工具 | [`01_installation/lab-node.1.md`](01_installation/lab-node.1.md) |
| **`lab-discover(1)`** | 動態實機遙測事實採集探針 | [`01_installation/lab-discover.1.md`](01_installation/lab-discover.1.md) |

---

## 🛠️ 2. 日常運維 App ([`02_operations/`](02_operations))
> 叢集安裝完成後的常態性維運工具，用於巡檢、登入、備份、升級、狀態監控與 IaC 狀態同步。

| 指令 (CLI Command) | 概要說明 (Description) | 實體手冊路徑 (Manual File) |
| :--- | :--- | :--- |
| **`lab-status(1)`** | 叢集即時狀態儀表板與零信任金鑰稽核 | [`02_operations/lab-status.1.md`](02_operations/lab-status.1.md) |
| **`lab-ssh(1)`** | 智慧 SSH 派發與四階段金鑰輪轉 | [`02_operations/lab-ssh.1.md`](02_operations/lab-ssh.1.md) |
| **`lab-backup(1)`** | 宣告式節點設定檔備份與災難復原 | [`02_operations/lab-backup.1.md`](02_operations/lab-backup.1.md) |
| **`lab-config(1)`** | 本機 Dotfiles 與 Shell 環境管理器 | [`02_operations/lab-config.1.md`](02_operations/lab-config.1.md) |
| **`lab-upgrade(1)`** | 多節點並行軟體包更新與補丁維護 | [`02_operations/lab-upgrade.1.md`](02_operations/lab-upgrade.1.md) |
| **`lab-info(1)`** | 感官事實抽取與 Markdown 文件生成 | [`02_operations/lab-info.1.md`](02_operations/lab-info.1.md) |
| **`lab-tools(1)`** | 互動式運維 TUI 選單終端 | [`02_operations/lab-tools.1.md`](02_operations/lab-tools.1.md) |
| **`lab-apply(1)`** | 宣告式模板編譯器與代碼同步工具 | [`02_operations/lab-apply.1.md`](02_operations/lab-apply.1.md) |
| **`lab-diff(1)`** | 配置漂移比對工具 (Drift Inspector) | [`02_operations/lab-diff.1.md`](02_operations/lab-diff.1.md) |

---

## 💻 3. 開發者環境與測試主控台 ([`03_development/`](03_development))
> 開發者與 AI 代理人專用工具，用於本機工作區工具鏈就緒、以及測試沙箱/Dagger 驗證調度。

| 指令 (CLI Command) | 概要說明 (Description) | 實體手冊路徑 (Manual File) |
| :--- | :--- | :--- |
| **`lab-dev-setup(1)`** | 開發者與 AI 工作區環境引導工具 | [`03_development/lab-dev-setup.1.md`](03_development/lab-dev-setup.1.md) |
| **`lab-test(1)`** | 沙箱測試控制台與多發行版整合驗證引擎 | [`03_development/lab-test.1.md`](03_development/lab-test.1.md) |
| **`lab-man(1)`** | 終端互動式指令手冊瀏覽器 | [`03_development/lab-man.1.md`](03_development/lab-man.1.md) |
