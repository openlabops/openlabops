---
id: lab-compiler
title: "Manifest Compiler (lab-diff & lab-apply)"
sidebar_position: 4
---

# `lab-diff` & `lab-apply` — Declarative Manifest Compiler

**Entrypoints:** `bin/lab-diff`, `bin/lab-apply` → **Engine:** `engine/compiler.py`

The manifest compiler renders Jinja2-style templates from `templates/` against a site manifest (`conf/openlab.manifest.yml` or `--manifest FILE`) and synchronizes downstream federation repositories.

## `lab-diff`

Compares rendered templates against current downstream federation repositories in dry-run mode without writing any files.

```bash
lab-diff [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR]
```

## `lab-apply`

Renders and writes `group_vars/all.yml`, `ansible/inventory/hosts.yml`, `ssh-config`, `backup_profiles.yml`, and Gitea Actions workflows to the target downstream directory tree.

```bash
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX]
          [--base-dir DIR] [--create-dest-dirs] [--ops-internal]
```

| Flag | Description |
| :--- | :--- |
| `--manifest FILE` | Path to the site YAML manifest. |
| `--dest-prefix PREFIX` | Downstream repository prefix (e.g., `openlab-`). |
| `--base-dir DIR` | Target parent directory containing `<prefix>operations`, `<prefix>configs`, `<prefix>secrets`, `<prefix>workflows`. |
| `--create-dest-dirs` | Create target downstream directories if they do not yet exist. |
| `--ops-internal` | Apply rendered files directly into internal repository paths (skipped during `lab-init`, which compiles into `/tmp`). |
| `--apply` | Write rendered changes (omitting `--apply` performs a dry-run diff). |
