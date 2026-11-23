---
id: lab-compiler
title: "マニフェストコンパイラ (lab-diff & lab-apply)"
sidebar_position: 4
---

# `lab-diff` & `lab-apply`

**エントリポイント:** `bin/lab-diff`, `bin/lab-apply` → **エンジン:** `engine/compiler.py`

```bash
lab-diff [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR]
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX]
          [--base-dir DIR] [--create-dest-dirs] [--ops-internal]
```

`templates/` をマニフェストに従ってレンダリングし、4リポジトリ連携構成へ同期します（`lab-init` 時は `/tmp` 配下へコンパイル）。
