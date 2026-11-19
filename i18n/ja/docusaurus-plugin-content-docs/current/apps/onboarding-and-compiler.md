---
id: onboarding-and-compiler
title: 導入・インベントリ・コンパイラ
sidebar_position: 1
---

# 導入・インベントリ・コンパイラ CLI

`bin/` 配下に配置され、Day-0 ブートストラップ、動的ノード登録、ハードウェア検出、マニフェストコンパイル、サンドボックステストを担当します。

---

## `lab-init`

**エンジン：** `engine/initialize.py`

Day-0 対話型初期化コマンダー。`archinstall` のように対話形式でサイト意図を収集（または保存済みマニフェストで無人構築）し、永続管理鍵の生成、Gitea 4リポジトリ連携と Act Runner の構築を行い、`conf/openlab.manifest.yml` を出力します。

```bash
lab-init [--lang {zh_TW,en_US,ja_JP}] [--manifest FILE] [--non-interactive]
         [--with-gitea-runner] [--with-remote-dev] [--skip-nodes HOSTS]
```

* `--lang`：ウィザードおよびクラスターのロケールを指定（`en_US`、`zh_TW`、`ja_JP`）。
* `--manifest`：エクスポート済みマニフェスト YAML を用いた無人 Day-0 構築。
* `--legacy-key`：混在環境での初期接続用レガシー SSH 秘密鍵パス。
* `--with-gitea-runner`：`ansible-core` 内蔵 Gitea Act Runner コンテナを構築・設定。
* `--with-remote-dev`：リモート開発コンテナを構築・プロビジョニング。
* `--skip-nodes`：スキップするホスト名をカンマ区切りで指定。

---

## `lab-node`

**エンジン：** `tools/lib/lab_node.py`（`bin/lab-node` -> `tools/bin/lab-node`）

動的ノード登録およびインベントリ管理。分類属性のみを `conf/nodes/<hostname>.json` に保存（ハードウェアテレメトリは混在させない）し、`ansible/inventory/hosts.yml` を即時コンパイルします。

```bash
lab-node {add,remove,list,sync}
```

* **`add <IP/Host> [--user USER]`**：SSH で対象ホストの OS とロールを検出し、`conf/nodes/<hostname>.json` を生成してインベントリを更新。
* **`remove <hostname>`**：ノードを廃止し、`conf/nodes/` およびスナップショットから即時削除。
* **`list`**：管理対象ノードと分類一覧を表示。
* **`sync`**：ライブ情報に基づきノードスナップショットを再同期・再計算。

---

## `lab-discover`

**エンジン：** `engine/discover.py`

リアルハードウェア・サービス事実収集ツール。`lab-node` とは厳密に分離されています。

```bash
lab-discover [--out-dir DIR] [--node HOST] [--manifest FILE]
```

* SSH 経由で軽量ネイティブプローブ（`engine/bootstrap_probe.sh`）を実行し、RAM、CPU、ディスク、コンテナ、待機ポート、`authorized_keys` フィンガープリントを `node-information/node_<hostname>.json` に収集します。

---

## `lab-diff` & `lab-apply`

**エンジン：** `engine/compiler.py`

宣言的マニフェストコンパイラおよび連携同期エンジン。

```bash
lab-diff [--manifest FILE] [--site SITE]
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR] [--create-dest-dirs]
```

* **`lab-diff`**：レンダリング結果と現在の下流リポジトリとの差分をプレビュー（書き込みなし）。
* **`lab-apply`**：`group_vars`、ワークフロー、サイトオーバーレイを生成し、下流 4 リポジトリへ同期します。

---

## `lab-dev-setup`

**スクリプト：** `bin/lab-dev-setup`

`ansible/playbooks/dev-environment.yml` を呼び出し、開発端末をワンコマンドでセットアップします。`ansible`、`cue`、`docker` を確認し、`ansible` が無い場合は `.venv` を自動作成して `ansible-core` を導入します。

```bash
lab-dev-setup [--check | -c] [--force | -f]
```

---

## `lab-test`

**スクリプト：** `bin/lab-test`

統合サンドボックス＆受け入れテストオーケストレーター。

```bash
lab-test [-m | --manual] [-a | --auto] [-g | --dagger] [--dr [TARGET]]
         [--kvm [PERSONA]] [-s | --status] [-r | --reset] [-d | --down]
         [-G {standalone,dind,external,local}] [--lang {zh_TW,en_US,ja_JP}]
```

* `--manual`：`mock-console`、`mock-gitea`、各 Linux ノードを起動し、`mock-console` の対話シェルに接続。
* `--auto`：完全自動 E2E 受け入れテスト（構築 $\rightarrow$ 登録 $\rightarrow$ ツール検証 $\rightarrow$ DR 訓練 $\rightarrow$ 破棄）。
* `--dagger`：Dagger DinD パイプラインを実行（`tests/e2e/test_dagger.py`）。
* `--dr [target]`：SHA-256 災害復旧訓練を実行（`tests/sandbox/dr_drill.sh`）。
