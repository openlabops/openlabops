---
id: lab-fleet-ops
title: "叢集佈建、升級與維運控制台"
sidebar_position: 6
---

# 叢集佈建、升級、設定與備份 CLI

* **`lab-setup`**（`tools/lib/lab_setup.py`）：列出或派發系統佈建步驟（`-l`, `-p`, `-t TARGET`, `-a`, `-s STEP`, `-m {gitea,local}`）。
* **`lab-upgrade`**（`tools/lib/lab_upgrade.py`）：多發行版套件升級儀表板（`-s` 循序串流、`-f` 強制）。
* **`lab-tools`**（`tools/lib/lab_tools.py`）：頂層 Curses TUI 維運控制台（含 `inspect-run <ID>` 與 `--plain`/`--no-tui`）。
* **`lab-backup`**（`tools/lib/lab_backup.py`）：閘道備份與共用設定廣播（`-a`, `-g`, `-b`, `-s SOURCE`）。
* **`lab-config`**（`tools/lib/lab_config.py`）：雙向 GitOps 本機設定管理（`--init`, `--show`, `--diff`, `--update`, `--reset`, `--restore`）。
* **`lab-info`**（`tools/lib/lab_info.py`）：CMDB 硬體與套件遙測收集及 Markdown 手冊渲染（`-a`, `-d`, `-p`, `-r`）。
