# sync-package-inventory 工作流手冊 (Manual Package IaC Sync Workflow)

## 1. 工作流定位
[`workflows/sync-package-inventory.yml`](../../../workflows/.gitea/workflows/sync-package-inventory.yml) 是 OpenLabOps Homelab 針對軟體套件清冊與 Repo IaC (`host_vars`) 的**純手動驅動** CI/CD 執行通道。

---

## 2. 安全原則與觸發條件 (Security Principles)

> [!IMPORTANT]
> * **嚴禁過度自動化**：本工作流**絕不設定**任何定時排程（Cron）或 Git Push 自動觸發事件。
> * **純手動觸發 (`workflow_dispatch`)**：僅能由管理員在 Gitea 網頁手動點擊或透過 `lab-tools` 派發執行。
> * **預設唯讀安全防線**：輸入參數 `apply_sync` 預設為 `false`，即預設只進行線上主機現況與 `host_vars` 的差異比對，並在 Actions 記錄中輸出警告，**完全不變更儲存庫檔案**。只有當您手動勾選 `apply_sync=true` 時，Runner 才會提交變更至 Git。

---

## 3. 輸入參數規格 (Workflow Inputs)

| 參數名稱 | 類型 | 預設值 | 說明 |
| :--- | :---: | :--- | :--- |
| `target_hosts` | string | `servers` | 指定比對的目標伺服器群組或單一節點（例如 `servers`, `srv-node1`, `gw-node`） |

| `apply_sync` | boolean | `false` | 是否將檢測到的主機現狀回寫至 `host_vars/<hostname>.yml` 與資產清冊 |

---

## 4. 執行流程與產出 (Execution Lifecycle)

```mermaid
flowchart TD
    Trigger["手動觸發 (workflow_dispatch)"] --> Clone["檢出 openlab-ansible 與 openlab-configs"]
    Clone --> Key["配置 ansible.key 連線私鑰"]
    Key --> Playbook["執行 Ansible: sync-package-inventory.yml"]
    Playbook --> Check{"apply_sync 是否為 true 且有變更?"}
    Check -->|否 (預設)| EndReport["輸出 Actions 執行記錄與漂移報表 (0 寫入)"]
    Check -->|是| GitAnsible["git commit & push host_vars/ 至 openlab-ansible"]
    GitAnsible --> GitConfigs["git commit & push packages_*.json 至 openlab-configs"]
    GitConfigs --> Finish["完成雙向原子化寫入"]
```

---

## 5. 觸發方式 (Usage)

### 方式 1：Gitea Actions 網頁手動觸發
1. 登入 Gitea 進入 `OpenLabOps/openlab-workflows`。
2. 點擊 **Actions** 標籤 ➡️ 選擇 **Manual Sync Package Inventory & IaC Drift Check**。
3. 點選 **Run workflow**，依需要輸入 `target_hosts` 並選擇是否勾選 `apply_sync`。

### 方式 2：透過 `lab-tools` 終端控制台派發
```bash
# 1. 互動選單派發
lab-tools
# 選取「📋 手動比對/同步全網節點 IaC 套件清冊 (Audit & Sync Package IaC)」

# 2. CLI 一鍵派發 (預設純比對)
lab-tools sync-iac srv-node1
```
