---
id: zero-dep-runner-model
title: "ゼロ依存標準ライブラリと Act Runner"
sidebar_position: 6
---

# ゼロ依存 Python 標準ライブラリと Gitea Act Runner モデル

## `[INV-01]` 外部 Python パッケージ依存ゼロ

すべてのエンジン（`engine/*.py`）およびツール（`tools/lib/*.py`）は Python 3 標準ライブラリのみで動作します（`pip` / `requests` / `pyyaml` / `paramiko` 不使用）。

## 集中型 Gitea Act Runner 実行

管理対象ノードや操作端末に `ansible-core` をインストールする必要はありません。`lab-ssh` / `lab-setup` / `lab-upgrade` などが Gitea API 経由で `<prefix>-workflows` をトリガーし、Gitea Act Runner コンテナが Playbook を実行します。
