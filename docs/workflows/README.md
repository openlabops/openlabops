# Homelab Workflows 文件導覽 (Documentation Index)

本目錄包含 `openlab-workflows` 儲存庫的所有架構規範、工作流操作指南、腳本說明及驗證審計報告。

---

## 結構與導覽 (Directory Structure)

```
docs/
├── architecture/                   # 核心系統設計與架構導覽
│   ├── workflows-guide.md         # Gitea Actions 工作流整體清單與設計細節
│   └── ssh-key-mapping.md         # SSH 金鑰在各節點與 CI/CD 之對應拓撲
├── workflows/                      # 個別工作流深度說明
│   └── sync-package-inventory.md  # 軟體包清單 IaC 差異比對與同步工作流
├── scripts/                        # 輔助腳本與 Git Hooks 說明
│   └── post-push-trigger.md       # Git post-push 自動觸發 Gitea Workflow 腳本
├── reports/                        # 執行報告與 CI/CD 驗證記錄
└── review/                         # 金鑰輪換代碼與流程審計存檔
    ├── lab.md                     # Lab 金鑰輪換審計
    ├── git-openlab.md            # Git-openlab 版控金鑰審計
    └── openlab.md                # OpenLabOps 主機金鑰審計
```

---

## 快速跳轉 (Quick Links)

- **工作流總覽與觸發方式**：參見 [Gitea Actions 工作流指南](workflows-guide.md)。
- **IaC 軟體包手動比對與同步**：參見 [軟體包清單 IaC 差異比對與同步說明](sync-package-inventory.md)。
- **Git 自動化觸發 Hook**：參見 [Post-Push Trigger Script 說明](post-push-trigger.md)。
- **SSH 拓撲與金鑰輪換**：參見 [SSH Key Mapping 拓撲表](../security/ssh-key-mapping.md)。
