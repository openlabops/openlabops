# OpenLabOps Operations Engine ドキュメントハブ (`docs/ja/`)

> **Language / 語言 / 言語**: [English](../README.md) | [繁體中文](../zh_TW/README.md) | **日本語**

> 本ディレクトリでは OpenLabOps Operations Engine の技術仕様書およびユーザーマニュアルを管理しています。

---

## ユーザーマニュアル (`user_manual/`)

対話型マニュアルブラウザ `./bin/lab-man` から直接閲覧できます（`LAB_LANG=ja_JP` または日本語ロケール環境で自動選択されます）：

### 1. インストール・ノード登録 (`user_manual/01_installation/`)
* [`lab-init(1)`](user_manual/01_installation/lab-init.1.md): Day-0 クラスター初期化ウィザード
* [`lab-node(1)`](user_manual/01_installation/lab-node.1.md): 動的ノード登録・PTY プローブウィザード
* [`lab-discover(1)`](user_manual/01_installation/lab-discover.1.md): 全ノードのハードウェア事実および SSH 鍵監査プローブ

### 2. 日常運用 (`user_manual/02_operations/`)
* [`lab-status(1)`](user_manual/02_operations/lab-status.1.md): クラスター健全性・90日鍵年齢・`authorized_keys` 監査ダッシュボード
* [`lab-ssh(1)`](user_manual/02_operations/lab-ssh.1.md): 対話型 SSH 接続セレクタ
* [`lab-info(1)`](user_manual/02_operations/lab-info.1.md): 単一ノードのテレメトリ詳細ビューア
* [`lab-backup(1)`](user_manual/02_operations/lab-backup.1.md): 宣言的設定バックアップおよび GitOps 同期ツール
* [`lab-upgrade(1)`](user_manual/02_operations/lab-upgrade.1.md): マルチスレッド・マルチディストリビューションパッケージ更新ツール
* [`lab-config(1)`](user_manual/02_operations/lab-config.1.md): ローカル dotfiles および GitOps 設定同期
* [`lab-diff(1)`](user_manual/02_operations/lab-diff.1.md): マニフェストと生成結果の差分検証ツール
* [`lab-apply(1)`](user_manual/02_operations/lab-apply.1.md): 宣言的マニフェストのコンパイルと適用
* [`lab-tools(1)`](user_manual/02_operations/lab-tools.1.md): ツールチェーンのバージョン確認と同期管理

### 3. 開発・テスト (`user_manual/03_development/`)
* [`lab-dev-setup(1)`](user_manual/03_development/lab-dev-setup.1.md): 開発者ワークステーション環境構築ツール
* [`lab-test(1)`](user_manual/03_development/lab-test.1.md): マルチディストリビューション Linux テストサンドボックス
* [`lab-man(1)`](user_manual/03_development/lab-man.1.md): 対話型マニュアルブラウザ
