---
id: sensory-cmdb-decoupling
title: "感官硬體探測與清冊分類解耦"
sidebar_position: 5
---

# 感官硬體探測與清冊分類解耦

OpenLabOps 嚴格分離「**Ansible 執行所需的節點分類**」與「**機器當下的硬體/服務遙測狀態**」。

## 兩條獨立管線

| 面向 | 清冊分類 (`lab-node` / `classifier.py`) | 感官 CMDB (`lab-discover` / `bootstrap_probe.sh`) |
| :--- | :--- | :--- |
| **輸出路徑** | `conf/nodes/<hostname>.json` 與 `ansible/inventory/hosts.yml` | `node-information/node_<hostname>.json`（位於 `<prefix>-configs`） |
| **收錄內容** | `hostname`、`primary_ip`、`os_family`、`distribution`、`node_category`、`capabilities` | CPU、RAM、磁碟、網卡與 CIDR、監聽埠、Docker 容器、`authorized_keys` 指紋 |
| **是否含硬體遙測** | **絕不收錄**（確保清冊 diff 乾淨且可重現） | **收錄**（作為 CMDB 與安全稽核基準） |

## 多發行版分類引擎（`engine/classifier.py`）

`classifier.py` 以純 Python 標準庫讀取 `conf/nodes/*.json`（執行期零 CUE 依賴），並自動編譯 `ansible/inventory/hosts.yml`：
* **支援發行版**：Arch Linux、Debian、Ubuntu、Oracle Linux、Alpine Linux、VMware Photon OS 及一般 systemd Linux。
* **角色分群**：`servers`、`dev`、`desktop`、`storage`、`hypervisor`。
* **網段分群**：Flat LAN（`192.168.1.0/24`）或自訂站點網段。
