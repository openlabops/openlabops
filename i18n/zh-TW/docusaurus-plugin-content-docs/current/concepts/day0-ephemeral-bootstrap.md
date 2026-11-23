---
id: day0-ephemeral-bootstrap
title: "Day-0 臨時引導與 /tmp 隔離"
sidebar_position: 2
---

# Day-0 臨時引導與 `/tmp` 工作區隔離

## 為何採用 `/tmp` 隔離

若在孵化器倉庫直接執行 `lab-init` 而未隔離，會覆寫受版控的範本檔（`conf/openlab.manifest.yml`、`ansible/group_vars/all.yml`、`tools/conf/tools.config.json`），並殘留節點 JSON 檔案。

為確保母體倉庫永遠乾淨：

1. **`LAB_INIT_WORK_DIR`（`/tmp/lab_init_work_*`）**：
   `engine/initialize.py` 啟動時於 `/tmp` 建立臨時工作區，並透過 `atexit` 於結束時自動清理。
   * `engine/onboard.py`（`_get_nodes_dir()`）與 `engine/classifier.py` 偵測到 `LAB_INIT_WORK_DIR` 時，會將 `conf/nodes/*.json`、`current.json` 與 `ansible/inventory/hosts.yml` 寫入 `/tmp`。
   * `export_site_manifest()` 將站點清單寫入 `/tmp`，`engine/compiler.py` 亦將下游倉庫編譯至 `/tmp/.../compiled`（不使用 `--ops-internal`）。
   * `push_fresh_configs_and_secrets_to_gitea()` 直接將 `/tmp` 內編譯好的產物推送至 Gitea `configs` 與 `secrets`。
2. **臨時引導金鑰（`/tmp/lab_bootstrap_keys/`）**：
   * 於 `/tmp` 生成無 `from="..."` IP 限制的臨時 Ed25519 金鑰對（`[INV-02]`），絕不寫入 `~/.ssh/`。
   * Day-0 期間即使管理機已存在 `~/.ssh/<target_user>.key`，`onboard_node()` 仍會優先採用傳入的 `ephemeral_pubkey` 開門。
3. **PTY 擬人互動引擎（`execute_pty_ssh`）**：
   透過 Python 內建 `pty` 模組分配真實控制終端，自動處理 SSH 密碼、`sudo` 密碼與 host key 確認，不依賴 `sshpass` 或 `pexpect`。
4. **SSH 限流退避重試（`_run_ssh_with_backoff`）**：
   遇到 `kex_exchange_identification`、`Connection reset by peer`、`Connection timed out` 等暫時性交握限流錯誤時自動短暫退避重試，避免觸發 `MaxStartups` 或防火牆限流。
