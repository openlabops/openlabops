# Gitea Actions 工作流與模組架構指南 (Workflows & Composite Actions Guide)

本文件規範 OpenLabOps Homelab 全網 CI/CD 自動化工作流之 **Code / Config 分離架構** 與 **Composite Actions 模組再利用體系**。

---

## 1. 架構核心理念：Code 與 Config 徹底解耦

在傳統的 CI/CD 設計中，各工作流往往充斥著重複的 `apk add` 套件安裝、冗長的 `git clone` 腳本、手動寫入 `~/.ssh/` 的私鑰權限控制，以及硬編碼的伺服器 IP 與主機名。此種「腳本雜揉」反模式導致維護成本高昂且容易產生配置漂移。

本架構全面落實 **Code 與 Config 分離**：
* **Code (邏輯抽象)**：將環境初始化、多庫聯邦檢出、SSH 鑑權注入、Ansible 執行調度、Git 差分推送與金鑰生成等通用操作，封裝為純淨、具輸入/輸出合約之 **Composite Actions (`.gitea/actions/`)**。
* **Config (宣告式工作流)**：工作流檔案 (`.gitea/workflows/*.yml`) 回歸純宣告本質，僅負責定義：
  1. 觸發事件 (`on: push`, `workflow_dispatch`, `repository_dispatch`)。
  2. 執行節點與標籤 (`runs-on: ansible`)。
  3. 參數注入矩陣與環境變數對應 (`with:`, `env:`, `secrets`)。

---

## 2. 七大通用 Composite Actions 模組庫

所有 Action 均存放於 `.gitea/actions/`（並建立頂層符號連結 `actions -> .gitea/actions` 便於引用）：

| Action 名稱 | 相對路徑 | 職責與輸入參數 (Inputs Contract) | 產出效果 |
| :--- | :--- | :--- | :--- |
| **`setup-environment`** | `./.gitea/actions/setup-environment` | • `extra_pkgs`: 額外需安裝的 Alpine 套件 (預設空) | 自動安裝標準工具鏈 (`git`, `openssh-client`, `ansible`, `rsync`, `python3`, `py3-pip`)；收緊 `~/.ssh` 權限至 0700/0600；停用 HostKey 互動提問。 |
| **`checkout-federation`** | `./.gitea/actions/checkout-federation` | • `repos`: 以空格分隔之聯邦倉庫列表 (如 `"openlab-ansible openlab-secrets"`)<br>• `dest_dir`: 檢出根目錄 (預設 `.` 或 `/tmp`)<br>• `depth`: 檢出深度 (預設 `1`)<br>• `gitea_host`: Gitea 伺服器 (預設 `${{ vars.GITEA_HOST \|\| 'gitea.lab' }}`)<br>• `org_name`: 組織名稱 (預設 `${{ vars.ORG_NAME \|\| 'OpenLabOps' }}`)<br>• `token`: 存取權杖 (相容 `MASTER_TOKEN` / `BOT_TOKEN`) | 批次淺層檢出指定聯邦倉庫，徹底消除硬編碼 IP/網域名稱。 |
| **`setup-ssh-auth`** | `./.gitea/actions/setup-ssh-auth` | • `key_name`: 私鑰檔名 (如 `ansible.key`, `id_user.key`)<br>• `source_dir`: 秘密存放庫目錄 (預設 `openlab-secrets/ssh-key`)<br>• `target_dir`: 注入目標 (預設 `~/.ssh`) | 符合 `[INV-02]` 零私鑰入庫鐵律；從 Secrets 倉庫提取私鑰並自動賦予 `0600` 嚴格權限。 |
| **`run-ansible-playbook`** | `./.gitea/actions/run-ansible-playbook` | • `playbook`: 劇本相對路徑<br>• `inventory`: 主機清單路徑 (預設 `openlab-ansible/inventory/hosts.yml`)<br>• `target_hosts`: 限制目標主機 (`-l`)<br>• `extra_vars`: 額外變數 (`-e`)<br>• `tags` / `skip_tags`: 執行/略過標籤 | 標準化 Playbook 調度引擎，自動注入 `ANSIBLE_HOST_KEY_CHECKING=False`，輸出乾淨執行紀錄。 |
| **`git-sync-commit`** | `./.gitea/actions/git-sync-commit` | • `target_dir`: 目標倉庫目錄<br>• `commit_msg`: 提交訊息 (自動附加 `[skip ci]`)<br>• `author_name` / `author_email`: 提交者身分<br>• `branch`: 推送分支 (預設 `main`) | 冪等性檢測：若無實質變更則自動略過；有變更則自動配置身分、提交並推送。 |
| **`generate-key-pair`** | `./.gitea/actions/generate-key-pair` | • `output_path`: 產出私鑰完整路徑<br>• `comment`: 公鑰標籤/備註<br>• `key_type`: `ed25519` (預設) 或 `rsa`<br>• `key_bits`: `4096` (RSA 專用) | 生成標準化、乾淨的加密金鑰對，自動設定 `0600` 權限。 |
| **`execute-federation-playbook`** | `./.gitea/actions/execute-federation-playbook` | • `playbook`: 劇本名稱<br>• `key_name`: 所需管理私鑰<br>• `target_hosts`: 目標主機<br>• `extra_vars`: 參數變數 | **一站式高階 Action**：自動串接環境準備、Ansible 庫與 Secrets 庫檢出、SSH 鑑權注入至 Playbook 執行完畢，達成 1 步完成常規自動化。 |

---

## 3. 工作流重構模式範例對比

### 傳統雜揉模式 (Anti-Pattern)
```yaml
# 舊式：指令繁瑣、環境脆弱、硬編碼 IP
steps:
  - run: apk add --no-cache git openssh-client ansible
  - run: git clone http://oauth2:${{ secrets.MASTER_TOKEN }}@192.168.1.90:3000/OpenLabOps/openlab-ansible.git
  - run: git clone http://oauth2:${{ secrets.MASTER_TOKEN }}@192.168.1.90:3000/OpenLabOps/openlab-secrets.git
  - run: |
      mkdir -p ~/.ssh && chmod 700 ~/.ssh
      cp openlab-secrets/ssh-key/ansible.key ~/.ssh/
      chmod 600 ~/.ssh/ansible.key
  - run: ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i openlab-ansible/inventory/hosts.yml openlab-ansible/playbooks/test.yml
```

### 新型宣告式分離模式 (Clean Declarative Pattern)
```yaml
# 新式：高階複用、參數可攜、乾淨優雅
steps:
  - name: 檢出工作流倉庫 (Self Checkout)
    run: git clone --quiet --depth 1 http://oauth2:${{ secrets.MASTER_TOKEN || secrets.BOT_TOKEN }}@${{ vars.GITEA_HOST || 'gitea.lab' }}/${{ vars.ORG_NAME || 'OpenLabOps' }}/openlab-workflows.git .

  - name: 一鍵執行 Homelab 劇本
    uses: ./.gitea/actions/execute-federation-playbook
    with:
      playbook: "playbooks/test-connectivity.yml"
      key_name: "ansible.key"
      target_hosts: "${{ github.event.inputs.target_hosts || 'all' }}"
      token: ${{ secrets.MASTER_TOKEN || secrets.BOT_TOKEN }}
```

---

## 4. 17 大工作流矩陣與模組對照

| 工作流檔案 | 用途說明 | 觸發方式 | 所調用之 Composite Actions |
| :--- | :--- | :--- | :--- |
| **`test-connectivity.yml`** | 全網主機連通性檢測 | 手動派發 | `execute-federation-playbook` |
| **`system-base-setup.yml`** | 節點基礎環境與使用者初始化 | 手動派發 | `execute-federation-playbook` |
| **`pull-docker-compose.yml`** | 容器服務拉取與滾動重啟 | 手動/事件觸發 | `execute-federation-playbook` |
| **`deploy-openlab-tools.yml`** | 全網主機佈署 `openlab-tools` CLI | 手動/代碼推送 | `execute-federation-playbook` |
| **`deploy-ssh-keys.yml`** | 全網公鑰分發與授權收斂 | 手動派發 | `execute-federation-playbook` |
| **`deploy-wsl-key.yml`** | 派發管理員個人工作站公鑰 | 手動派發 | `execute-federation-playbook` |
| **`deploy-host-key.yml`** | 單一主機動態注入專屬公鑰 | 手動派發 | `execute-federation-playbook` |
| **`revoke-host-key.yml`** | 吊銷並清除特定主機之授權金鑰 | 手動派發 | `execute-federation-playbook` |
| **`harden-lab-ssh-2fa.yml`** | 啟用強化 SSH 雙因子身分驗證 | 手動派發 | `execute-federation-playbook` |
| **`sync-node-config.yml`** | 採集節點組態並同步 Dotfiles | 手動/事件觸發 | `setup-environment`, `checkout-federation`, `setup-ssh-auth`, `run-ansible-playbook`, `git-sync-commit` |
| **`sync-package-inventory.yml`** | 動態採集節點原生安裝套件清冊 | 手動/排程 | `setup-environment`, `checkout-federation`, `setup-ssh-auth`, `run-ansible-playbook`, `git-sync-commit` |
| **`update-node-docs.yml`** | 採集節點硬體遙測事實並生成手冊 | 手動/排程 | `setup-environment`, `checkout-federation`, `setup-ssh-auth`, `run-ansible-playbook`, `git-sync-commit` |
| **`sync-workflow.yml`** | 同步工作流與 Actions 至中央倉庫 | 代碼推送/手動 | `setup-environment`, `checkout-federation`, `git-sync-commit` |
| **`rotate-lab-keys.yml`** | 管理金鑰 (`ansible.key`) 4 階段安全輪換 | 手動派發 | `setup-environment`, `checkout-federation`, `generate-key-pair`, `setup-ssh-auth`, `run-ansible-playbook`, `git-sync-commit` |
| **`rotate-openlab-keys.yml`** | 儲存金鑰 (`id_user.key`) 4 階段輪換 | 手動派發 | `setup-environment`, `checkout-federation`, `generate-key-pair`, `setup-ssh-auth`, `run-ansible-playbook`, `git-sync-commit` |
| **`rotate-git-openlab-keys.yml`**| API 版控金鑰 REST 輪換 | 手動派發 | `setup-environment`, `checkout-federation`, `generate-key-pair`, `git-sync-commit` |

---

## 5. 動態網域名稱與組織參數化注入規範

為確保工作流可無縫移植至測試沙箱（如 `172.28.0.2:3000`）與不同組織命名的站點，全網 Action 與工作流全面落實 Fallback 參數化：

1. **伺服器主機名**：`${{ vars.GITEA_HOST || 'gitea.lab' }}`
2. **組織代碼**：`${{ vars.ORG_NAME || 'OpenLabOps' }}`
3. **存取權杖相容性**：`${{ secrets.MASTER_TOKEN || secrets.BOT_TOKEN }}`

若 Gitea Repository Variables 未特別宣告，系統自動回退至 OpenLabOps 內部正式網域；若於沙箱或客製化環境執行，只需於 Gitea Web UI 設定 `GITEA_HOST` 變數即可全網生效，無需修改任何工作流代碼。


