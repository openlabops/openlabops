---
id: onboarding-and-compiler
title: 納管、庫存與編譯工具
sidebar_position: 1
---

# 納管、庫存與編譯 CLI

位於 `bin/` 目錄下，負責 Day-0 集群引導、動態節點納管、硬體探測、Manifest 編譯與沙箱測試。

---

## `lab-init`

**底層引擎：** `engine/initialize.py`

Day-0 互動式初始化指揮官。比照 `archinstall` 設計，透過互動精靈收集站點意圖（或讀取既有 Manifest 無人值守建立），產生永久管理金鑰、建立 Gitea 四庫聯邦與 Act Runner，並匯出落地 `conf/openlab.manifest.yml`。

```bash
lab-init [--lang {zh_TW,en_US,ja_JP}] [--manifest FILE] [--non-interactive]
         [--with-gitea-runner] [--with-remote-dev] [--skip-nodes HOSTS]
```

* `--lang`：指定精靈與集群語系（`en_US`、`zh_TW`、`ja_JP`）。
* `--manifest`：從匯出的 Manifest YAML 執行無人值守 Day-0 建置。
* `--legacy-key`：指定混合場景初始連線用之舊版 SSH 私鑰路徑。
* `--with-gitea-runner`：建置並設定內建 `ansible-core` 的 Gitea Act Runner 容器。
* `--with-remote-dev`：佈建遠端開發容器。
* `--skip-nodes`：以逗號分隔指定要略過的主機名稱。

---

## `lab-node`

**底層引擎：** `tools/lib/lab_node.py`（`bin/lab-node` 指向 `tools/bin/lab-node`）

動態節點納管與庫存管理。僅將分類屬性寫入 `conf/nodes/<hostname>.json`（絕不混入硬體遙測），並即時編譯 `ansible/inventory/hosts.yml`。

```bash
lab-node {add,remove,list,sync}
```

* **`add <IP/Host> [--user USER]`**：透過 SSH 探測目標主機 OS 與角色分類，寫入 `conf/nodes/<hostname>.json` 並重新編譯庫存。
* **`remove <hostname>`**：除役節點並自 `conf/nodes/` 與所有快照中即時抹除。
* **`list`**：列出所有已納管節點與分類角色。
* **`sync`**：依據即時事實重新同步並計算節點快照。

---

## `lab-discover`

**底層引擎：** `engine/discover.py`

感官真實硬體與服務事實採集器，與 `lab-node` 嚴格解耦。

```bash
lab-discover [--out-dir DIR] [--node HOST] [--manifest FILE]
```

* 透過 SSH 執行輕量原生探針（`engine/bootstrap_probe.sh`），採集 RAM、CPU、磁碟、容器、監聽埠與 `authorized_keys` 指紋至 `node-information/node_<hostname>.json`。

---

## `lab-diff` 與 `lab-apply`

**底層引擎：** `engine/compiler.py`

宣告式 Manifest 編譯器與聯邦同步器。

```bash
lab-diff [--manifest FILE] [--site SITE]
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR] [--create-dest-dirs]
```

* **`lab-diff`**：比對編譯後產物與下游聯邦倉庫之差異（唯讀不寫入）。
* **`lab-apply`**：渲染 `group_vars`、工作流與站點覆蓋檔，並同步至下游四庫（`<prefix>-operations`、`<prefix>-workflows`、`<prefix>-configs`、`<prefix>-secrets`）。

---

## `lab-dev-setup`

**腳本：** `bin/lab-dev-setup`

調用 `ansible/playbooks/dev-environment.yml` 完成工作站一鍵就緒。自動確認 `ansible`、`cue`、`docker` 齊備；若缺少 `ansible`，則自動建立 `.venv` 並自舉安裝 `ansible-core`。

```bash
lab-dev-setup [--check | -c] [--force | -f]
```

---

## `lab-test`

**腳本：** `bin/lab-test`

整合沙箱與自動化驗收編排器。

```bash
lab-test [-m | --manual] [-a | --auto] [-g | --dagger] [--dr [TARGET]]
         [--kvm [PERSONA]] [-s | --status] [-r | --reset] [-d | --down]
         [-G {standalone,dind,external,local}] [--lang {zh_TW,en_US,ja_JP}]
```

* `--manual`：啟動 `mock-console`、`mock-gitea` 與多發行版節點後，自動進入 `mock-console` 互動終端。
* `--auto`：執行全自動無人值守驗收（建置 $\rightarrow$ 納管 $\rightarrow$ 工具驗證 $\rightarrow$ 災難演練 $\rightarrow$ 銷毀）。
* `--dagger`：執行 Dagger DinD 容器流水線（`tests/e2e/test_dagger.py`）。
* `--dr [target]`：執行 SHA-256 災難復原演練（`tests/sandbox/dr_drill.sh`）。
