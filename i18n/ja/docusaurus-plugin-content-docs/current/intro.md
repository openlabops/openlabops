---
id: intro
slug: /
title: OpenLabOps Wiki
sidebar_position: 1
---

# OpenLabOps：ゼロ依存・宣言的 Homelab 運用エンジン

**OpenLabOps** は、現代の Homelab およびプライベート Linux サーバー群向けに設計されたオープンソースの GitOps 運用コントロールハブです。**100% Python 3 標準ライブラリ**とステートレスな Ansible プレイブックのみで構築されており、サードパーティ製 Python パッケージ（`NO pip`、`NO requests`、`NO pyyaml`）を一切使わずに、Day-0 インタラクティブ導入、3段階ゼロダウンタイム SSH 鍵ローテーション、リアルタイムハードウェア検出、宣言的 GitOps 同期を提供します。

## クイックスタート (Quickstart)

```bash
# 1. 管理ワークステーションでワンラインインストール
curl -fsSL https://raw.githubusercontent.com/openlabops/openlabops/main/scripts/install.sh | bash

# 2. Day-0 対話型オンボーディングウィザードを起動
lab-init

# 3. ノードの動的追加とクラスター状態の監視
lab-node add 192.168.1.50 --user admin
lab-status -k
lab-tools
```

## コアアーキテクチャ不変条件 (Invariants)

| ID | 原則 | 強制仕様 |
| :--- | :--- | :--- |
| **INV-01** | **外部依存ゼロ** | 100% Python 3 標準ライブラリ（`urllib.request`, `json`, `subprocess`, `pathlib`, `curses`）と組み込み YAML パーサーを使用。 |
| **INV-02** | **リポジトリ内平文認証情報ゼロ** | 秘密鍵や API トークンを Git に保存せず、管理端末の `~/.ssh/` と `ssh-agent` を直接利用。 |
| **INV-03** | **3層分離アーキテクチャ** | 不変の `core` 仕様、宣言的 `site` 意図、動的 `node` テレメトリを厳密に分離。 |
| **INV-04** | **リアルセンサーテレメトリ** | 不変仕様は `schema/*.cue` で検証し、実機情報は実行時に純粋な JSON（`conf/nodes/*.json`）として収集。 |

## Wiki ナビゲーション

* **[システムアーキテクチャ](./architecture)** — 3層分離、4リポジトリ連携と権限分離、Flat LAN、CUE 不変条件。
* **[セキュリティポリシーと鍵ライフサイクル](./security)** — 標準鍵ロール、3段階ゼロダウンタイムローテーション、`from="..."` IP 制限、`lab-boot-sync` ロックアウト防止。
* **[テスト手法とサンドボックス原理](./testing)** — 本番ツール検証原則、Dagger DinD、マルチディストリビューション Docker サンドボックス、PTY シミュレーター、SHA-256 DR 訓練。
* **[Antigravity Vibe Coding と AI SRE](./methodology)** — 仕様優先の人機協調開発フローと、既存境界を活かした `AGY-Remote` の安全な SRE 運用。
* **[CLI アプリと内部実装](./apps/onboarding-and-compiler)** — すべての `lab-*` コマンドおよび補助スクリプトの詳細な使い方と内部仕様。
