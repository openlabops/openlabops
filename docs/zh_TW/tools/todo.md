# OpenLabOps Homelab 待辦事項與演進清單 (TODO.md)

本文件專注追蹤**目前進行中與未來規劃之功能、優化與演進項目**。  
> 歷史已完成里程碑請查閱：`歷史里程碑與架構演進歸檔庫`。

---

## 狀態圖例
- 🔴 **高優先級 (P0 / Critical)**：影響核心架構、關鍵安全或自動化演進。
- 🟡 **中優先級 (P1 / Important)**：影響運維效率、體驗一致性或長期可維護性。
- 🟢 **低優先級 (P2 / Enhancement)**：體驗優化、進階美化或邊緣相容性增強。

---

## 進行中與規劃清單 (Active & Upcoming Roadmap)

### 一、 核心自動化與測試驗收 (Automation & E2E Testing Contract)
- [x] 🔴 **Dagger E2E 雙軌實機全功能測試整合 (消除虛擬 `-h` 假測試)**
  - **完成進度**：重構 `tests/e2e/test_dagger.py`，全面落實 `[INV-09]` 生產工具驗證契約。直接於隔離沙箱驅動 `mock-console`，拉起多發行版容器集群（Arch, Photon, Oracle, Debian, Alpine, Storage），全自動執行 Day-0 納管、硬體動態遙測、維運工具鏈部署、AOT Bytecode 預編譯與三階段零停機金鑰輪替，達成雙庫（`openlabops` 與 `openlabops`）100% 實機通過。
  - **架構報告**：產出專屬驗收審查報告 `docs/reviews/mock-fleet-dagger-e2e-report.md` 並同步更新開源端雙語測試手冊。
- [x] 🔴 **OpenLabOps 5 庫聯邦解耦與 group_vars / 符號連結標準化**
  - **完成進度**：補足 `openlabops/ansible/group_vars/`，標準化 `ansible_user: ansible` 與庫存符號連結 `inventory/group_vars`，修復動態分類器 `classifier.py` 子網別名命名對齊，打通開源母體自舉回歸。

### 二、 現代化 TUI 互動介面與版本維護 (Modern TUI & Version Lifecycle)
- [x] 🔴 **導入原生標準庫高階 TUI (Terminal User Interface)**
  - **完成進度**：已於 `lab-tools` 與 `lab-tools` 完整實裝雙欄自適應 Curses TUI 引擎（`tools/lib/core/ui_curses.py`），具備左側 6 大分類導航、右側動作卡片與即時狀態列，支援方向鍵與 Vim 鍵（`↑`/`↓`/`j`/`k`/`Tab`/`Enter`）。
  - **自動降級合約**：自動偵測 `sys.stdin.isatty()` 與 `--plain`/`--no-tui` 參數。在腳本、CI/CD、AI 代理人或非 TTY 管道中自動無縫切換為傳統序列式文字選單，確保非人類操作 100% 零中斷相容。
- [x] 🔴 **BSD `dialog` / `bsdinstall` 風格 TUI 與階層勾選清單 (Modern TUI Upgrade)**
  - **完成進度**：
    - `ui_checklist()`：純 Python 標準庫實裝 dialog 勾選清單，支援 `[Space]` 空白鍵切換 `[X]`、`[a]` 全選/全不選、`[Enter]` 提交。
    - `ui_form()`：實作單卡片整合式多欄位表單，支援 `[↑ / ↓ / Tab]` 切換、即時鍵入、`Backspace` 刪除與密碼隱碼遮罩。
    - `select_target_hosts()`：實作兩層級主機選擇器（Level 1: 全部節點 / 依群組或發行版 / 自訂勾選；Level 2: 群組成員細部微調）。
    - 全面擴充套用至 `lab-node` / `lab-node`、`lab-backup` / `lab-backup`、`lab-upgrade` / `lab-upgrade`、`revoke-host-ssh-key`。
- [x] 🔴 **節點動態脫離管控與金鑰精確拔除 (Node Decommissioning & Zero-Trust Key Revocation)**
  - **完成進度**：實作安全脫離管控流程，直接調用金鑰吊銷機制精準比對專案部署之 Ansible 管理公鑰，僅移除匹配行；實機上個人日常私鑰與自訂公鑰 100% 完好保留。
- [x] 🟡 **OpenLabOps 開源合規與社群致敬 (NOTICE & Upstream Credits)**
  - **完成進度**：於根目錄建立專屬 `NOTICE` 檔案，並在 `README.md` 增設 `💖 Acknowledgments & Upstream Credits` 專區，正式致敬 Ansible、OpenSSH、CUE、Dagger、Gitea 與各大 Linux 發行版。
- [x] 🟡 **多層級更新與版本管理體系確立 (Self-Update & Fleet Upgrade)**
  - **完成進度**：確立四大維度更新能力：本機維運工具鏈語意化版本比對與自更新 (`sync-ops-tools -c / -f`)、全網受控節點工具鏈批次推播 (`sync-ops-tools -n servers`)、全叢集作業系統套件更新儀表板 (`lab-upgrade` / `lab-upgrade`)，以及宣告式架構差異比對與編譯套用 (`lab-diff` / `lab-apply`)。

### 三、 外部聯邦、容器與 Git 存取 (External Federation & GitOps)
- [x] 🟡 **外部 GitHub `docker-compose` 與業務倉庫管理模式定調**
  - **架構決策**：業務容器倉庫無須侵入合入維運母體。AGY (Google Antigravity) 工作環境需要時直接以 `git clone` 導入至 Active Workspace 即可。
  - **母體職責**：維運母體僅專注核心基礎設施、節點基線與 **Git 存取金鑰生命週期（GitHub SSH-Key Update / Rotation）**。目前 `rotate-git-keys` 已原生對接 GitHub API (`POST /user/keys`) 與連線驗證。
- [ ] 🔴 **常駐 `antigravity-sre` 容器化架構設計與事件驅動部署**
  - **目標**：以事件驅動方式（平日 0 Token 消耗）在容器內常駐 AI SRE 監控代理。
  - **觸發機制**：僅在捕獲 `✖ ROGUE` 未授權公鑰、磁碟使用率 >90% 或 CI/CD 構建失敗時，才主動喚醒並執行排查與建議。

### 四、 SRE 監控、可觀測性與自動化演練 (SRE & Reliability)
- [x] 🔴 **自動化災難復原演練整合進測試控制台 (Automated DR Restore Drill in `lab-test`)**
  - **架構決策 (不用定期排程)**：依據架構規範，災難復原演練**不設置定時背景排程 (No Periodic Cron)**，杜絕無謂的運算資源浪費與排程干擾；改為**按需（On-Demand）發起**並完全整合至測試沙箱控制台。
  - **完成進度**：
    - 於 `./bin/lab-test` 與 `./bin/lab-test` 實裝主選單 `[9] 🛡️ 災難復原演練 (DR Drill)` 與 `--dr` 命令列旗標。
    - 透過正式劇本 `ansible/playbooks/backup-node.yml` 採集節點宣告式備份至 Controller Vault。
    - 於多發行版節點（`mock-arch`, `mock-photon`, `mock-debian`）模擬毀滅性資料損壞（檔案刪除與故障注入）。
    - 驅動 `ansible/playbooks/restore-node.yml` 執行自動化還原，實測對比前後 SHA-256 簽名，達成 100% Bit-for-Bit 無損還原（Zero Data Loss）。
- [ ] 🔴 **即時主動告警通道 (Alert Webhook Integration)**
  - **目標**：建立輕量級 Webhook 告警模組（支援 Discord / Telegram），純 Python 標準庫發送。
  - **告警事件**：節點儲存分割區使用率 >90%、捕獲未授權後門公鑰、主機斷線或升級失敗時立即推播。
- [ ] 🟡 **每日排程配置漂移主動檢測 (Proactive Configuration Drift Detection Cron)**
  - **目標**：建立清晨定時執行的 Gitea Actions 工作流，主動比對受控節點即時狀態與 Git SSOT。
  - **檢測範疇**：未受控手動安裝套件、SSL/TLS 憑證即將過期、私鑰年齡 >90 天或未提交之配置漂移。
*(註：原本規劃之「金絲雀發布 (Canary Rollout)」經架構審查確認不符合異質節點 Homelab 拓撲；現行架構之「三階段先驗證後清除金鑰輪換合約」配合「多發行版容器沙箱預檢」已達成 100% 零中斷防禦，故除役)*

### 五、 延伸架構事項與擴充生態 (Extensions & Gap Analysis)
- [ ] 🟡 **Appliance 擴充採集器實裝 (`extensions/collectors/`)**
  - **目標**：依據 `EXT-JSON-V1` 規格，正式實作 Proxmox VE、TrueNAS SCALE 與 Network Network Controller 採集器，完成非標準設備的納管閉環。
- [ ] ⏸️ **多操作者稽核日誌 (Audit Trail) - [Pending]**
  - **決策**：Homelab 單人/小團隊維運無本機多租戶日誌需求。暫緩實作，待未來引進專屬外部 Log Server 與 AGY SRE 審計功能時再行外掛。
*(註：原本規劃之「離線部署套件包 (Air-Gapped Offline Bundle)」經架構審查除役：Homelab 本質仰賴內網連通性進行集中控制，內網離線環境早已由自建 Gitea 滿足，母體無須製造無內網可用之離線安裝包)*

---

*本清單保持精簡動態更新。最後修訂時間：2026-10-30。*
