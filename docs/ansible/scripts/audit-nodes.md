# 節點即時審計與自動化腳本說明文件 (Node Audit & Scripts Specification)

本文件詳細說明 [`openlab-ansible/scripts/`](../../../ansible/scripts) 目錄下的所有節點審計與自動化觸發腳本之架構、採集內容與跨平台執行邏輯。

---

## 1. 腳本職責與平台分工

| 腳本名稱 | 實作語言 | 目標系統 | 核心職責 | 呼叫來源 |
| :--- | :---: | :--- | :--- | :--- |
| **[`audit-node-linux.py`](../../../ansible/scripts/audit-node-linux.py)** | Python 3 | Photon OS, Oracle Linux, Arch Linux | 採集 CPU/Memory/網卡IP/磁碟空間/Systemd 服務/Docker 運行容器 | [`update-node-docs.yml`](../../../ansible/playbooks/update-node-docs.yml) |
| **[`post-push-trigger.sh`](../../../ansible/scripts/post-push-trigger.sh)** | `/bin/sh` | 各節點 Docker Compose Git 目錄 | 安裝於 `.git/hooks/post-push`，當本機 push 後自動觸發 CI 廣播 | [`install-docker-compose-hook.yml`](../../../extensions/playbooks/install-docker-compose-hook.yml) |

---

## 2. 審計資料輸出規範 (JSON Schema)

所有審計腳本皆遵循統一的 JSON 頂層架構，產出結構化的 `node_<hostname>.json`，作為 CMDB 資料來源：

```json
{
  "node_type": "linux",
  "hostname": "Base",
  "generated_at": "2026-10-20 16:22:15",
  "system": {
    "os": "VMware Photon OS/Linux",
    "kernel": "6.12.107-4.ph5-esx",
    "cpu": { "model": "Intel Xeon", "cores": 4 },
    "memory": { "total_mb": 7968, "used_mb": 3558, "free_mb": 4411 },
    "default_gateway": "192.168.1.254 dev eth0"
  },
  "network_interfaces": [
    { "name": "eth0", "mac": "00:50:56:10:06:01", "ips": ["192.168.1.230/24"] }
  ],
  "disks": [
    { "mount": "/", "size_gb": 40.0, "used_gb": 12.3, "use_percent": "31%" }
  ],
  "systemd_services": [
    { "name": "docker.service", "load": "loaded", "active": "active", "sub": "running" }
  ],
  "docker_containers": [
    { "name": "nginx_proxy_manager", "image": "jc21/nginx-proxy-manager:latest", "status": "running" }
  ]
}
```

---

## 3. 部署與執行流程

在 [`playbooks/update-node-docs.yml`](../../../ansible/playbooks/update-node-docs.yml) 中：
1. **清理歷史殘留**：透過 `ansible.builtin.file` 清理 `/tmp/node_{{ inventory_hostname }}.json` 與 `/tmp/audit-node.py`。
3. **執行採集**：執行 `python3 /tmp/audit-node.py "/tmp/node_{{ inventory_hostname }}.json"`。
4. **回傳與渲染**：抓取遠端 JSON 至本地 `openlab-configs/node-information/`，並調用 `render_node_doc.py` 產出人類可讀的 Markdown 手冊至 Private-Vault。
