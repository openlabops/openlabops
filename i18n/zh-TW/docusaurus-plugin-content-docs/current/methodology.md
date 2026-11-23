---
id: methodology
title: Antigravity Vibe Coding 與 AI SRE 協作
sidebar_position: 5
---

# Antigravity Vibe Coding 與 AI 輔助 SRE

**OpenLabOps** 全專案皆透過 **Google Antigravity (AGY) Vibe Coding** 開發完成——由人類架構師定義硬性不變量與設計意圖，並由 AI 代理人於嚴格邊界內負責實作、測試與端到端驗證。

---

## 1. 人機協作開發模式

傳統的 Vibe Coding 在基礎設施專案上容易出現套件膨脹、架構漂移與跳過測試等問題。OpenLabOps 透過三大機制讓 AI 開發既快速又可控：

### A. 機器可讀工程契約 (`AGENTS.md`)
所有架構紀律皆寫入 `AGENTS.md` 作為不可妥協的不變量：
* **零外部依賴 (`[INV-01]`)**：強制 AI 僅使用 Python 3 標準函式庫。
* **零明文憑證 (`[INV-02]`)**：嚴禁 AI 寫死或提交任何私鑰與 Token。
* **正式工具驗證 (`[INV-09]`)**：禁止 AI 編寫造假測試或吞滅例外，所有修改必須在真實 Docker/Dagger 沙箱通過。

### B. 規格先行三階段流水線 (`[INV-10]`)

```mermaid
flowchart LR
    W["1. 開發白板<br/>.agents/WHITEBOARD.md<br/>人類意圖與決策"] -->|"吸收並清空"| D["2. 正式規格<br/>docs/ + AGENTS.md + schema/*.cue<br/>cue vet 驗證"]
    D -->|"實作"| C["3. 程式碼與劇本<br/>engine/ + tools/ + ansible/"]
    C -->|"驗收"| T["4. 真實沙箱<br/>unittest + Dagger DinD + 災難演練"]
```

1. **白板輸入**：人類開發者將想法或需求寫入 `.agents/WHITEBOARD.md`。
2. **文件與規格對齊**：AI 先將決策整合進正式 `docs/` 與 `schema/*.cue`（通過 `cue vet ./schema/`），隨即清空白板。
3. **實作與真實驗證**：規格確定後才修改 Python/Ansible 程式碼，並於單元測試與 Dagger 沙箱驗證。

---

## 2. 利用現有邊界讓 `AGY-Remote` 安全參與 SRE

正因為 OpenLabOps 在架構層已建立嚴密的安全與權限邊界，你可以放心地將 **AGY-Remote** 納入 Homelab 擔任 AI SRE 維運助手，而不必擔心權限失控或私鑰外洩。

### 部署 `AGY-Remote`
在 Day-0 初始化時加上 `--with-remote-dev` 即可建立遠端開發與 SRE 容器：
```bash
lab-init --with-remote-dev
```

### 安全邊界內的 AI SRE 實戰工作流

1. **全網健康與安全巡檢（唯讀）**：
   * `lab-status --json` — 取得結構化 JSON 叢集健康度遙測。
   * `lab-status -a` — 執行 `authorized_keys` 指紋稽核，揪出未授權金鑰。
   * `node-information/node_<hostname>.json` — 檢視即時記憶體、磁碟、容器與監聽埠狀態。
2. **CI/CD 失敗診斷**：
   * `lab-tools --plain inspect-run <ID>` — 免 TTY 直接拉取 Gitea Actions 執行錯誤日誌，無需對 Runner 開放原始 SSH 權限。
3. **受控修復派發**：
   * `AGY-Remote` 可透過 `lab-setup -s <step>`、`lab-upgrade` 或 `lab-ssh --rotate-ansible` 經由 `ci-bot` 派發預審核之 GitOps 工作流。
   * 由於 `ci-bot` **物理上無法修改** `openlab-operations`，AI SRE 無法擅自竄改 Ansible 劇本或存取 `openlab-secrets` 私鑰。
4. **變更前規格護欄**：
   * 任何 Manifest 或網段調整都必須先通過 `cue vet ./schema/` 驗證才能透過 `lab-diff` / `lab-apply` 渲染，搭配 `lab-boot-sync` 與三階段金鑰輪替，確保 AI 操作絕不會鎖死人類管理員。
