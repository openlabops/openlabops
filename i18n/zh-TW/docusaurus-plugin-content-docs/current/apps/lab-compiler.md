---
id: lab-compiler
title: "宣告清單編譯器 (lab-diff & lab-apply)"
sidebar_position: 4
---

# `lab-diff` & `lab-apply` — 宣告式清單編譯器

**入口點：** `bin/lab-diff`、`bin/lab-apply` → **引擎：** `engine/compiler.py`

依據站點清單（`conf/openlab.manifest.yml` 或 `--manifest FILE`）渲染 `templates/` 內的範本，並同步至下游四庫聯邦。

## 語法

```bash
lab-diff [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR]
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX]
          [--base-dir DIR] [--create-dest-dirs] [--ops-internal]
```

* **`lab-diff`**：乾跑（Dry-run）比對渲染結果與下游倉庫差異。
* **`lab-apply`**：渲染並寫入 `group_vars/all.yml`、`hosts.yml`、`ssh-config`、`backup_profiles.yml` 與 Gitea Actions workflows（`lab-init` 期間編譯至 `/tmp`，不使用 `--ops-internal`）。
