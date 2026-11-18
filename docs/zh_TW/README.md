# OpenLabOps Operations Engine 文件中心 (docs/)
> 本目錄集中管理 OpenLabOps Operations Engine 所有程式說明與使用者操作手冊。  
> 依照職責分門別類，杜絕散落，實體參數全數對齊 `conf/` 宣告檔。

---

## 📚 目錄總覽與兩大核心分類 (Documentation Taxonomy)

本手冊中心分為兩大板塊：
1. **[程式說明與架構手冊 (Program Documentation)](#一程式說明與架構手冊-program-documentation)**：包含系統不變量、架構總綱、Ansible IaC、CLI 工具核心、CI/CD 與安全金鑰規格。
2. **[使用者操作手冊 (User Manual)](#二使用者操作手冊-user-manual)**：包含安裝納管、日常維運、開發測試等 man 風格操作手冊。

---

## 一、程式說明與架構手冊 (Program Documentation)

### 1. 架構與總綱 (architecture/)
* [架構總綱：Code + Config 分離實施規劃書](architecture/code-config-separation-plan.md)
* [戰略定位與初始化工作流規範書 (Incubator & Initialization Spec)](architecture/incubator-and-initialization-spec.md)
* `標準擴充體系與外部整合架構規格書 (Extensions & External Integrations Spec)`
* [聯邦母體全量合成與 OpenLabOps 開源蒸餾規格書 (Federation Synthesis & Distillation Spec)](architecture/federation-synthesis-spec.md)
* `OpenLabOps 蒸餾脫敏與中性化規格書 (OpenLab Distillation & Sanitization Spec)`
* [虛擬叢集測試沙箱與多發行版驗收規格書 (Dagger / Sandbox Spec)](architecture/dagger-testing-environment-spec.md)
* [模板編譯渲染架構與中性語意模組規範 (Template Compiler & Neutral Roles)](architecture/template-compiler-and-neutral-roles.md)
* [劇本參數抽象化與聲明式擴充架構規格書 (Playbook Parameterized Abstraction Spec)](architecture/playbook-parameterized-abstraction-spec.md)
* [全網調度對應全表：Tools CLI/API ➔ Workflows ➔ Playbooks ➔ 參數規格書 (Master Invocation Matrix)](architecture/tools-workflow-playbook-mapping.md)
* `受變數影響之劇本清單與聲明式抽象化探討 (Variable-Driven Playbooks Analysis)`
* `五庫檔案對照與架構分工規範 (Repository Ecosystem Map)`
* [Ansible IaC 架構手冊](architecture/ansible-architecture.md)
* [CLI 工具庫架構手冊](architecture/tools-architecture.md)
* [套件資訊管理規格書](architecture/package-information-spec.md)
* [節點動態納管與自動預分類架構規格書](architecture/node-onboarding-and-ingestion-spec.md)

### 2. 安全金鑰與機密管理 (security/)
* [全網 SSH 金鑰定義與安全連線總規範 (SSOT)](security/ssh-keys-spec.md)
* [CI/CD 機密變數與權限邊界規格書 (Action Secrets Spec)](security/action-secrets-spec.md)
* [CI/CD 工作流與金鑰對應拓撲 (Workflow Key Mapping)](security/ssh-key-mapping.md)

### 3. Ansible IaC 自動化規格 (ansible/)
* [Ansible 模組與劇本總覽](ansible/README.md)
* [7 大解耦角色規格書 (Roles Modularization Spec)](ansible/roles-modularization-spec.md)
* [Inventory 拓撲與多維自動預分類規範](ansible/inventory.md)
* [自訂套件事實搜集模組](ansible/custom-package-facts.md)
* **Playbooks 劇本規格 (ansible/playbooks/)**：
  * [Playbooks 調度架構總覽](ansible/playbooks/playbooks-overview.md)
  * [新節點佈署劇本 (Node Provisioning)](ansible/playbooks/node-provisioning.md)
  * [管理端點引導劇本 (Endpoint Bootstrap)](ansible/playbooks/endpoint-bootstrap.md)
  * [個人化 Dotfiles 部署劇本](ansible/playbooks/dotfiles-deployment.md)
  * [系統套件管理劇本](ansible/playbooks/package-management.md)
* **審計腳本規格 (ansible/scripts/)**：
  * [節點審計腳本規格 (Linux)](ansible/scripts/audit-nodes.md)
  * [主機套件變數同步腳本](ansible/scripts/sync-host-package-vars.md)

### 4. Python CLI 工具庫規格 (tools/)
* [CLI 工具庫架構總覽](tools/README.md)
* [工具庫 TODO 開發路線圖](tools/todo.md)
* [版本規格與規範](tools/versioning-spec.md)
* [安裝與依賴規範 (Zero-Dependency Python)](tools/installation-spec.md)
* [Curses TUI 規格手冊](tools/curses-tui-spec.md)
* [SSH 工具整合手冊](tools/ssh-tools-integration.md)
* **個別維運指令手冊**：
  * [lab-status 叢集儀表板](tools/lab-status.md)
  * [lab-ssh 互動式連線器](tools/lab-ssh.md)
  * [lab-info 節點詳細查詢](tools/lab-info.md)
  * [lab-backup 自動備份腳本](tools/lab-backup.md)
  * [lab-setup 環境初始化](tools/lab-setup.md)
  * `rotate-keys 金鑰輪替工具`
  * [endpoint-ssh-tools 外部端點工具](tools/endpoint-ssh-tools.md)
  * [lab-node 節點動態納管指令](tools/lab-node.md)
* **核心函式庫 (tools/core/)**：
  * [TUI 互動選單引擎](tools/core/ui-menu.md)
  * [TUI 主題與顏色規範](tools/core/ui-theme.md)
  * [Gitea REST API 客戶端](tools/core/gitea-api.md)
  * [版本控制與檢查核心](tools/core/version.md)
  * [Markdown 節點手冊渲染器](tools/core/render-node-doc.md)

### 5. Gitea Actions CI/CD 規格 (workflows/)
* [CI/CD 工作流設計指引](workflows/README.md)
* [工作流詳細架構與排程](workflows/workflows-guide.md)
* [套件庫同步工作流](workflows/sync-package-inventory.md)
* [Push 事件後續自動觸發腳本](workflows/post-push-trigger.md)
* `Actions 執行驗證報告書`

### 6. 架構審查與驗收報告 (reviews/)
* `沙箱多發行版 Dagger E2E 實機全功能自動化驗收報告 (Dagger E2E Mock Fleet Testing Report)`
* `歷史里程碑與已完成架構演進歸檔庫 (Historical Milestones Archive)`
* `隱私防護、聲明式備份、CUE 一致性與全維度安全審查報告 (Comprehensive Audit Report)`
* `沙箱多發行版自動化驗收與人類擊鍵模擬報告 (Mock Fleet Testing Report)`
* `系統積木化重構與節點動態納管架構收斂報告`
* `四大金鑰自動化輪替與部署管道綜合審查報告`

---

## 二、使用者操作手冊 (User Manual)

使用者操作手冊集中維護於 [`docs/user_manual/`](user_manual/README.md)，採用標準 Linux Man-page 風格組織，可直接在終端透過 `./bin/lab-man` 互動檢視：

### 1. 安裝與納管手冊 (user_manual/01_installation/)
* [`lab-init(1)`](user_manual/01_installation/lab-init.1.md)：Day-0 叢集引導、五庫聯邦建立與金鑰輪轉向導
* [`lab-node(1)`](user_manual/01_installation/lab-node.1.md)：單節點互動引導、PTY 活體探針與分類向導
* [`lab-discover(1)`](user_manual/01_installation/lab-discover.1.md)：控制台全網節點硬體事實與金鑰即時審計

### 2. 維運與管理手冊 (user_manual/02_operations/)
* [`lab-status(1)`](user_manual/02_operations/lab-status.1.md)：全網健康度、90天金鑰年齡與後門公鑰檢測儀表板
* [`lab-ssh(1)`](user_manual/02_operations/lab-ssh.1.md)：SSH 互動連線選擇器與自動環境辨識
* [`lab-info(1)`](user_manual/02_operations/lab-info.1.md)：單一節點遙測詳情與卡片檢視
* [`lab-backup(1)`](user_manual/02_operations/lab-backup.1.md)：宣告式設定備份與 GitOps 同步工具
* [`lab-upgrade(1)`](user_manual/02_operations/lab-upgrade.1.md)：多線程多發行版套件更新儀表板
* [`lab-config(1)`](user_manual/02_operations/lab-config.1.md)：本機備份設定與 GitOps 雙向同步控制
* [`lab-diff(1)`](user_manual/02_operations/lab-diff.1.md)：宣告檔與現行狀態雙向差異比對器
* [`lab-apply(1)`](user_manual/02_operations/lab-apply.1.md)：宣告意圖編譯並套用至下游庫存與組態
* [`lab-tools(1)`](user_manual/02_operations/lab-tools.1.md)：工具鏈全域版本檢查與同步管理器

### 3. 開發與測試手冊 (user_manual/03_development/)
* [`lab-dev-setup(1)`](user_manual/03_development/lab-dev-setup.1.md)：開發者工作站一鍵宣告式環境就緒
* [`lab-test(1)`](user_manual/03_development/lab-test.1.md)：多發行版 Linux 虛擬測試沙箱與親自手 Key 體驗向導
* [`lab-man(1)`](user_manual/03_development/lab-man.1.md)：終端互動式指令手冊與維運文件瀏覽器
