# OpenLabOps Homelab - Gitea Actions Secrets 定義與權限規範手冊 (Action Secrets Specification)

本文件定義 OpenLabOps Homelab 全網 CI/CD 自動化（Gitea Actions）所依賴之機密憑證（Secrets）的**掛載位置、命名慣例、使用場景、精準授權範圍（Scopes）與生成指引**，作為全網 Actions 安全配置與 Token 權限隔離之單一信任來源（SSOT）。

---

## 1. 核心安全架構與權限隔離原則 (Security Architecture)

> [!IMPORTANT]
> 1. **最高權限留雲端，外部終端僅持受限 Token (Zero High-Privilege on Edge)**：
>    - **`MASTER_TOKEN`（全域最高權限）**：**只允許留存在 Gitea Actions Secrets 內部**，外部實體機器（如 `control-node`、筆電或本機腳本）嚴禁落地或儲存此 Token。
>    - **`CI_TOKEN`（外部觸發專用）**：本機終端、CLI 或外部自動化僅持有低權限的 `CI_TOKEN`，其功能**僅限於 Trigger Workflow**，無權讀寫全域金鑰或碰觸任何機密儲存庫。
> 2. **RBAC 帳號團隊隔離（克服 Gitea Token 缺乏單一倉庫 Scopes 的關鍵）**：
>    - Gitea 目前的 PAT 授權範圍無法拆分「僅限觸發 Actions」與「限定單一倉庫」。
>    - 因此，**`CI_TOKEN` 必須由專屬的非管理員機器人帳號（`ci-bot`）簽發**，且在 `OpenLabOps` 組織中透過專屬團隊（`CI-Dispatchers`）**限制其僅能存取 `openlab-workflows` 儲存庫**。對 `openlab-secrets` 等其他機密倉庫徹底隱形（404/403）。
> 3. **統一掛載於「組織層級 (Organization Level)」**：
>    - 轄下所有受控儲存庫（`openlab-workflows`、`openlab-ansible`、`openlab-secrets`、`openlab-configs`、`openlab-tools`）皆隸屬 **`OpenLabOps` 組織**。
>    - 所有 Actions Secrets 統一在組織層級配置，專案工作流程自動繼承，**嚴禁在單一儲存庫分散建立**，避免版本失步與權限碎裂。
> 4. **只進不出 (Write-Only) 原則**：
>    - Gitea Actions Secret 儲存後由系統非對稱加密，Web UI 無法檢視明文。需變更時一律直接貼上新值進行覆蓋更新（Overwrite）。

---

## 2. 全網 Actions Secrets 規範對照總表 (Master Secrets Matrix)

| Secret Name | 掛載層級 (Location) | 存放位置 (Storage Place) | 簽發帳號 / 身分 | 相關工作流程 | 用途說明 (Purpose) | 必要授權範圍 (Required Scopes) | 安全等級 |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: |
| **`MASTER_TOKEN`** | 組織層級 (`OpenLabOps`) | **僅留存於 Actions Secrets**<br/>*(嚴禁落地至終端設備)* | 管理員 (`labadmin`) | 全體 Workflows (所有自動化任務) | 擁有整個 OpenLabOps 組織的**最高管理權限**，用於：<br/>1. 自動檢出/提交私有倉庫代碼與金鑰<br/>2. 調用 Gitea API 寫入/刪除全網 SSH 公鑰<br/>3. 調用 Gitea Admin API 作為最高權限備援 | **Gitea PAT (Full Admin)**：<br/>• 勾選**所有權限** (`all` / `admin:all`)<br/>• 包含 `repo`, `org`, `user`, `admin` 等全域完整權限 | 🔴 最高 |
| **`GH_TOKEN`** | 組織層級 (`OpenLabOps`) | **僅留存於 Actions Secrets** | GitHub 帳號 (`labadmin`) | `rotate-git-openlab-keys.yml` | 專門用於向 GitHub 登記與清理使用者 SSH 公鑰，**嚴格禁止賦予其他無關權限** | **GitHub PAT (classic)**：<br/>• 務必使用 **Classic PAT**（Fine-grained 不支援個人公鑰）<br/>• 僅勾選 **`admin:public_key`**（涵蓋讀寫與刪除個人公鑰） | 🟡 嚴格受限 |
| **`CI_TOKEN`**<br/>*(非 Action Secret)* | 外部終端設備<br/>(`control-node`, CLI) | 部署於管理員端點本機<br/>*(如 `/usr/local/bin/openlab/.gitea_token`)* | 專用機器人 (**`ci-bot`**) | 供外部腳本/終端觸發 CI 流程 | **僅能 Trigger 工作流程**之受限 Token，外部終端即使外洩亦無法竄改金鑰或竊取機密 | **Gitea PAT (ci-bot 簽發)**：<br/>• Team 僅綁定 `openlab-workflows`<br/>• 僅勾選 `repository:write`<br/>• 物理無法存取 `openlab-secrets` | 🟢 最小權限 |

---

## 3. 已廢止 / 不需配置之項目說明 (Excluded & Deprecated Secrets)

以下項目依據 Homelab 架構優化已正式廢止或改由其他機制原生提供，**無需**在 Gitea Actions Secrets 中配置：

1. **`NETWORK_PASSWORD`（不需配置）**：
   - **替代方案**：節點拓撲與狀態收集腳本改為直接連線並讀取本機/容器底層之 **MongoDB 資料庫**，不再經由 HTTP API 透過密碼認證，因此廢止此 Secret。
2. **`ANSIBLE_KEY`（不需配置）**：
   - **替代方案**：Ansible 連線所需之 Master 私鑰直接自受控的 **`openlab-secrets` 儲存庫**（`ssh-key/ansible.key`）提取載入，無需在 Actions Secrets 內冗餘託管一份私鑰字串。

---

## 4. 各 Token 詳細配置與權限產生指引

### 4.1 `MASTER_TOKEN`（全域最高權限憑證）

* **掛載路徑**：`http://gitea.lab/org/OpenLabOps/settings/actions/secrets`
* **產生位置**：以管理員 `labadmin` 登入 ➔ 右上角頭像 ➔ **個人設定 (Settings)** ➔ **應用程式 (Applications)** ➔ **產生新 Token (Generate Token)**
* **Token 名稱建議**：`openlab-action-master-token`
* **授權設定**：
  - **勾選完整管理權限**（或全勾選：`repo`, `organization`, `user` 包括 `write:user`, `admin`）。
* **部署動作**：
  1. 產生並複製 Token 明文。
  2. 前往 `OpenLabOps` 組織設定 ➔ **Actions** ➔ **Secrets**。
  3. 建立或覆蓋 Secret 名稱：**`MASTER_TOKEN`**。

---

### 4.2 `GH_TOKEN`（GitHub SSH 公鑰管理專用）

* **掛載路徑**：`http://gitea.lab/org/OpenLabOps/settings/actions/secrets`
* **產生位置**：[GitHub Settings ➔ Developer Settings ➔ Personal Access Tokens ➔ Tokens (classic)](https://github.com/settings/tokens)
* **Token 名稱建議**：`openlab-ssh-key-sync-token`
* **Token 類型選擇（關鍵限制）**：
  - **務必選擇 `Personal Access Token (classic)`**。
  - ⚠️ **技術限制成因**：GitHub 的 Fine-grained PAT 目前權限範圍（Scope）僅綁定在「Repository」或「Organization」層級，**不支援存取或修改使用者個人層級的公鑰 API (`POST /user/keys`)**。因此要自動同步使用者 SSH Key，必須使用 Classic PAT。
* **授權設定 (最小權限原則)**：
  - **僅勾選**：**`admin:public_key`**（在 GitHub Classic 介面中直接勾選此項，即完整涵蓋讀取、新增與刪除個人 SSH 公鑰權限）。
  - **切勿勾選**：`repo`、`workflow`、`admin:org` 或任何其他無關權限，將外洩風險降至最低。
* **有效期限 (Expiration)**：
  - 建議設定明確效期（如 **90 天**），並配合安全金鑰輪替週期更新。
* **部署情境替代方案評估 (Deploy Keys vs. 個人全域公鑰)**：
  - **個人帳號公鑰（現行方案）**：若此 SSH Key 用於開發端點全域存取所有個人倉庫，使用 Classic PAT 同步至個人帳號是標準做法。
  - **專案專用 Deploy Key（替代方案）**：若輪替之 SSH Key 僅供 CI 存取特定 GitHub 倉庫，可改用該倉庫內部的 Deploy Keys（`Settings ➔ Deploy keys`），設定該 Key 僅具備單一 Repo 權限，完全免除產生任何全域 PAT。

#### 附錄：工作流程呼叫 GitHub REST API 實作範例
在 [`rotate-git-openlab-keys.yml`](../../../workflows/.gitea/workflows/rotate-git-keys.yml) 中，透過 `GH_TOKEN` 自動同步與清理公鑰之標準 API 呼叫：

```bash
# 1. 登記新 SSH 公鑰至個人帳號
KEY_TITLE="git-openlab-$(date +%Y%m%d%H%M%S)"
curl -s -X POST "https://api.github.com/user/keys" \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"${KEY_TITLE}\",\"key\":\"${NEW_PUB_KEY}\"}"

# 2. 查詢既有公鑰列表並比對舊金鑰 ID
KEYS_JSON=$(curl -s -X GET "https://api.github.com/user/keys" \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json")
OLD_KEY_ID=$(echo "${KEYS_JSON}" | jq -r ".[] | select(.key | contains(\"${OLD_PUB_KEY}\")) | .id")

# 3. 刪除過期舊公鑰
if [ -n "${OLD_KEY_ID}" ] && [ "${OLD_KEY_ID}" != "null" ]; then
  curl -s -X DELETE "https://api.github.com/user/keys/${OLD_KEY_ID}" \
    -H "Authorization: Bearer ${GH_TOKEN}" \
    -H "Accept: application/vnd.github+json"
fi
```

---

### 4.3 `CI_TOKEN` 與 `ci-bot` 團隊 RBAC 隔離配置指引

為克服 Gitea Token 無法指定單一倉庫權限的限制，必須結合「**專用 Bot 帳號 + 組織團隊倉庫限制**」實現真正的最小權限隔離：

#### Step 1: 確認 `ci-bot` 帳號非管理員
1. 管理員 `labadmin` 登入 ➔ 點擊右上角 **「站台管理 (Site Administration)」** ➔ **「使用者帳號 (User Accounts)」**。
2. 編輯 `ci-bot`，確認 **「管理員 (Administrator)」未勾選**。

#### Step 2: 在 `OpenLabOps` 組織中建立受限團隊
1. 進入組織團隊管理：`http://gitea.lab/org/OpenLabOps/teams`。
2. 檢查 `ci-bot` 是否在 `Owners`（所有者）團隊中，**若有必須立即移除**。
3. 點擊 **「建立新團隊 (New Team)」**：
   - **團隊名稱**：`CI-Dispatchers`
   - **倉庫存取權 (Repository Access)**：切換為 **「特定儲存庫 (Specific repositories)」**。
   - **倉庫勾選**：**僅勾選 `openlab-workflows`**（嚴禁勾選 `openlab-secrets`、`openlab-ansible` 等）。
   - **團隊權限 (Permissions)**：倉庫權限選擇 **「可寫入 (Write)」**（觸發 workflow dispatch 需寫入權限）。
4. 建立後，將 **`ci-bot`** 加入該團隊成員清單中。

#### Step 3: 由 `ci-bot` 簽發受限 Token
1. 登出，改以 **`ci-bot`** 帳號登入 Gitea。
2. 右上角頭像 ➔ **個人設定** ➔ **應用程式** ➔ 產生新 Token：
   - **名稱**：`openlab-cli-trigger-token`
   - **權限**：僅勾選 **`repository`**。
3. 複製產出的 Token，儲存至端點的 `/usr/local/bin/openlab/.gitea_token`（模式保持 `0600`）。

#### Step 4: 雙重隔離驗證測試
在端點執行以下指令驗證權限隔離是否成功：
```bash
# 1. 驗證無法存取機密庫 (預期必須回傳 404 或 403 阻斷)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: token <CI_TOKEN>" \
  http://gitea.lab/api/v1/repos/OpenLabOps/openlab-secrets
# 輸出: 404

# 2. 驗證可正常存取 workflows 庫 (預期必須回傳 200)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: token <CI_TOKEN>" \
  http://gitea.lab/api/v1/repos/OpenLabOps/openlab-workflows
# 輸出: 200
```

#### Step 5: 端點本地儲存與免密威脅模型評估 (Threat Model & No-Encryption Rationale)
> [!TIP]
> **決策定案：端點全面採用模式 `0600` 之明文 `.gitea_token`，不強制進行密碼加密。**

* **資安威脅模型實務評估 (Threat Modeling)**：
  1. **極高攻擊前置門檻**：端點憑證由 Linux 檔案系統權限 `0600` 保護（僅 `labadmin` 與 `root` 可讀）。攻擊者若能竊取此檔案，意味著該實體主機已被攻陷。
  2. **內網網路邊界防護**：Gitea（`http://gitea.lab`）僅運行於受控內網與 WireGuard VPN。攻擊者即使竊得 Token，若無法接入實體 LAN 亦毫無作用。
  3. **HTTP 傳輸層現實**：內網 Gitea 採用純 HTTP，若攻擊者具備內網嗅探與終端控制能力，本地加密無法抵禦網路層或更暴力的攻擊，屬於「偽安全感 (Security Theater)」。
  4. **爆炸半徑已被實體鎖死**：最核心的底牌在於 `ci-bot` 僅能接觸 `openlab-workflows`，即使 Token 外洩，攻擊者也**完全無法觸及 `openlab-secrets` 與全網 SSH 金鑰**。
  5. **開發與自動化體驗最佳化**：免密明文部署可確保 `lab_ctl`、Ansible、Cron 排程與 AI 輔助開發全程無阻斷、零密碼打擾，避免因非互動式終端（Non-TTY）遇到密碼提示而直接卡死或崩潰。

---

## 5. Gitea Web UI 操作圖解步驟（Secrets 管理）

### Step 1: 進入組織層級 Secrets 管理頁面
1. 登入 Gitea 網頁（`http://gitea.lab` 或 `http://gitea.lab:80`）。
2. 在頂端搜尋列或組織清單進入 **`OpenLabOps` 組織**。
3. 點選組織頁面右上角的 **「組織設定 (Settings)」**（齒輪圖示）。
   > **直達網址**：`http://gitea.lab/org/OpenLabOps/settings`
4. 點選左側選單的 **「Actions」** ➔ **「Secrets」**。

### Step 2: 建立或更新 Secret
1. 點擊右上角藍色按鈕 **「新增 Secret (Add Secret)」**。
2. **名稱 (Name)**：輸入大寫名稱（例如 `MASTER_TOKEN`、`GH_TOKEN`）。
3. **內容 (Content)**：貼上剛剛產生的 Token 明文。
4. 點擊 **「新增 Secret (Add Secret)」**。
5. 若要覆蓋既有 Secret，直接點擊該項目右側的 **「編輯」**（筆型圖示），輸入新內容儲存覆蓋即可。

---

## 6. 常見問題與排查指引 (Troubleshooting)

### Q1: 為什麼我在 `openlab-workflows` 等儲存庫設定裡看不到這些 Secrets？
* **解答**：因為它們全部配置在 `OpenLabOps` **組織層級**！Gitea 單一儲存庫的設定頁面只會列出「專屬於該儲存庫」的 Secret，組織共用 Secret 會被繼承但不會列在子頁面中。請一律至 `http://gitea.lab/org/OpenLabOps/settings/actions/secrets` 查閱。

### Q2: 執行 Workflow 時報錯 `token does not have required scope`？
* **解答**：代表目前 Gitea Secrets 內的 Token 在產生時缺少對應權限。依照本規範，將組織層級的 `MASTER_TOKEN` 替換為具備 Full Admin 權限的 Token 即可一勞永逸解決。

### Q3: `ci-bot` 的 Token 外洩了會有什麼後果？
* **解答**：因為已經透過 `CI-Dispatchers` 團隊進行倉庫實體隔離，攻擊者拿到該 Token 也只能向 `openlab-workflows` 觸發 Actions，**無法檢視、下載或修改 `openlab-secrets`、`openlab-ansible` 或 `openlab-configs` 中的任何檔案**，更無法讀取 Actions Secrets 內部的 `MASTER_TOKEN`，風險完全被限縮在安全邊界內。
