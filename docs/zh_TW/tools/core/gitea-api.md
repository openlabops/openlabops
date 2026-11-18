# Gitea API 核心庫模組說明文件

[`lib/core/gitea_api.py`](../../../../tools/lib/core/gitea_api.py) 負責呼叫 Gitea REST API 觸發 `workflow_dispatch` 工作流派發、執行追蹤與錯誤日誌診斷。

---

## 動態參數繼承與 Token 讀取機制

核心庫依據 [INV-03] 三層架構原則，所有 Gitea 調度參數優先繼承自 `lab-init` 所收集並落地之 Tier 2 站點宣告檔 (`conf/openlab.manifest.yml` / `conf/openlab.manifest.yml`) 與 `tools/conf/tools.config.json`：

- `GITEA_URL`：動態讀取自 `git_platform.host` 或 `~/.gitea_url`（預設為 `http://gitea.lab`）
- `REPO_OWNER`：動態讀取自 `git_platform.org`（組織名稱，預設為 `OpenLabOps` 或 `OpenLabOps`）
- `ACTION_REPO`：動態讀取自 `${repo_prefix}-workflows`（聯邦工作流倉庫，預設為 `openlab-workflows`）
- `ADMIN_USER`：動態讀取自 `cluster.admin_user`（管理員帳號，供過渡期候補對齊）
- `ANSIBLE_USER`：動態讀取自 `cluster.ansible_user`（自動化維運帳號，供金鑰輪換別名解析）
- `TOKEN_FILE`：預設為 `/usr/local/bin/openlab/.gitea_token` 或 `~/.gitea_token`（**標準部署：模式 `0600` 免密明文**）

> [!IMPORTANT]
> **Token 安全、RBAC 隔離與免密設計原則**：
> 1. **帳號隔離**：端點本機之 Token 必須依據 `Action Secrets 規範手冊`，由專用機器人帳號 **`ci-bot`** 簽發，透過 Gitea `CI-Dispatchers` 團隊將其權限嚴格死鎖於 `openlab-workflows`，徹底隔離 `openlab-secrets`。
> 2. **實務免密威脅模型**：由於 `gitea.lab` 為純內網 HTTP 服務，且存取需同時突破本機權限 (`0600`) 與 LAN/VPN 邊界，在爆炸半徑已被 RBAC 鎖死的前提下，**端點全面採用模式 `0600` 的明文 `.gitea_token`**，以確保 `lab-tools`、Ansible、Cron 排程與 AI 運維能夠無阻斷、零密碼打擾地全自動執行。

---

## API 端點 (API Endpoint)

```
POST {GITEA_URL}/api/v1/repos/{REPO_OWNER}/{ACTION_REPO}/actions/workflows/{workflow_file}/dispatches
```
Headers:
- `Authorization: token {TOKEN}`
- `Content-Type: application/json`

Payload:
```json
{
  "ref": "main",
  "inputs": { ... }
}
```

---

## 程式碼實作解說 (`core.gitea_api`)

使用 Python 原生 `urllib.request` 與 `json` 模組處理 HTTP 請求與 JSON 序列化，完全不依賴第三方庫。

支援四大核心功能：
1. **工作流派發與即時執行追蹤 (`gitea_dispatch`)**：
   - 預設 `wait=True`：派發後自動鎖定 Run ID，即時輪詢執行狀態與耗時。
   - 若成功完成：回傳 `True` 並輸出總耗時。
   - 若執行失敗：自動調用錯誤診斷模組並回傳 `False`。
2. **錯誤自動診斷與日誌反饋 (`display_run_error_feedback`)**：
   - 自動查詢該 Run 之失敗 Jobs (`/actions/runs/{id}/jobs`) 與失敗 Steps。
   - 直連 `/actions/jobs/{job_id}/logs` 提取原始執行日誌。
   - 智慧過濾系統建立/清理雜訊，精準截取致命錯誤（`fatal:`, `FAILED!`, `exitcode` 等 Root Cause 行）並輸出至終端。
3. **歷史執行查詢 (`get_action_runs` / `get_run_detail`)**。
4. **CLI 隨選診斷**：
   ```bash
   lab-tools inspect-run <run_id>
   ```

```python
from core.gitea_api import gitea_dispatch, display_run_error_feedback

# 派發並自動追蹤（出錯時自動印出具體錯誤訊息）
success = gitea_dispatch("deploy-host-key.yml", payload={"ref": "main", "inputs": {"host_name": "wsl"}})

# 手動對特定失敗 Run 進行日誌診斷
if not success:
    display_run_error_feedback(run_id=42)
```
