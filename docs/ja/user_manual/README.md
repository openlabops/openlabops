# OpenLabOps ユーザーマニュアル (`docs/ja/user_manual/`)

> **Language / 語言 / 言語**: [English](../../user_manual/README.md) | [繁體中文](../../zh_TW/user_manual/README.md) | **日本語**

ユーザーマニュアルは運用フェーズごとに 3 つのサブディレクトリに分類されており、`./bin/lab-man` または `./bin/lab-tools` から対話的に閲覧できます：

---

## 1. インストール・ノード登録 ([`01_installation/`](01_installation/))
> Day-0 クラスター構築、ローカル Gitea セットアップ、実機プローブ、動的ノード登録。

- [`lab-init(1)`](01_installation/lab-init.1.md) — Day-0 クラスター初期化ウィザード
- [`lab-node(1)`](01_installation/lab-node.1.md) — 動的ノード登録・構成ツール
- [`lab-discover(1)`](01_installation/lab-discover.1.md) — 実機ハードウェア・SSH 鍵テレメトリプローブ

## 2. 日常運用アプリ ([`02_operations/`](02_operations/))
> 日常運用：健全性ダッシュボード、SSH 鍵ローテーション、バックアップ、dotfiles、パッケージ更新。

- [`lab-status(1)`](02_operations/lab-status.1.md) — リアルタイムクラスター状態ダッシュボード & ゼロトラスト鍵監査
- [`lab-ssh(1)`](02_operations/lab-ssh.1.md) — 対話型 SSH ランチャー & 4 段階鍵ローテーション
- [`lab-setup(1)`](02_operations/lab-setup.1.md) — サーバー初期設定・コンテナ環境マウントツール
- [`lab-backup(1)`](02_operations/lab-backup.1.md) — 宣言的ノード設定バックアップ & 災害復旧
- [`lab-config(1)`](02_operations/lab-config.1.md) — ローカル Dotfiles & シェル環境マネージャー
- [`lab-upgrade(1)`](02_operations/lab-upgrade.1.md) — マルチノード並列パッケージ更新ツール
- [`lab-info(1)`](02_operations/lab-info.1.md) — ノードテレメトリ詳細ビューア & Markdown ドキュメント生成
- [`lab-tools(1)`](02_operations/lab-tools.1.md) — 対話型運用 TUI コンソール
- [`lab-apply(1)`](02_operations/lab-apply.1.md) — 宣言的テンプレートコンパイラ & 設定同期
- [`lab-diff(1)`](02_operations/lab-diff.1.md) — 設定ドリフト検査ツール

## 3. 開発・テストコンソール ([`03_development/`](03_development/))
> 開発者ワークステーション構築、マルチディストリビューションサンドボックス、マニュアルブラウザ。

- [`lab-dev-setup(1)`](03_development/lab-dev-setup.1.md) — 開発者 & AI ワークスペース構築ツール
- [`lab-test(1)`](03_development/lab-test.1.md) — マルチディストリビューションテストサンドボックス
- [`lab-man(1)`](03_development/lab-man.1.md) — 対話型ターミナルマニュアルブラウザ
