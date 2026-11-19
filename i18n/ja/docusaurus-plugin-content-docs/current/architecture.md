---
id: architecture
title: システムアーキテクチャ
sidebar_position: 2
---

# システムアーキテクチャ

OpenLabOps は「不変フレームワーク契約」「サイト宣言意図」「ライブノードテレメトリ」を厳格に 3 層へ分離し、権限境界が分離された 4 つの下流 GitOps リポジトリへ展開します。

```mermaid
flowchart TB
    subgraph Console["管理ワークステーション (~/.ssh Agent)"]
        CLI["ゼロ依存 Python CLI<br/>lab-init / lab-node / lab-status / lab-tools"]
        T1["Tier 1: コア仕様<br/>conf/core.manifest.yml + schema/*.cue"]
        T2["Tier 2: サイト意図<br/>conf/openlab.manifest.yml"]
        T3["Tier 3: ノードテレメトリ<br/>conf/nodes/*.json"]
    end

    subgraph Federation["4リポジトリ GitOps 連携"]
        OPS["openlab-operations<br/>Playbooks + エンジン"]
        WF["openlab-workflows<br/>CI/CD + Runner ディスパッチ"]
        CFG["openlab-configs<br/>CMDB + ノード事実"]
        SEC["openlab-secrets<br/>暗号化 Vault + 公開鍵"]
    end

    subgraph Fleet["管理対象 Flat LAN フリート (192.168.1.0/24)"]
        N1["サーバーノード<br/>Arch / Debian / Ubuntu"]
        N2["開発・デスクトップ端末<br/>Workstations + 起動時同期ガード"]
        N3["軽量・コンテナノード<br/>Alpine / Photon / Docker"]
    end

    CLI --> T1 & T2 & T3
    T3 -->|"hosts.yml をコンパイル"| OPS
    CLI -->|"ワークフロー起動 (ci-bot)"| WF
    WF -->|"読み取り専用チェックアウト"| OPS
    WF -->|"テレメトリ・マニュアルをプッシュ"| CFG
    WF -->|"鍵ポリシーを参照"| SEC
    WF -->|"SSH 経由で Ansible 実行"| Fleet
```

## 1. 3層分離モデル

1. **Tier 1 (`core`)：不変フレームワーク仕様**
   * `conf/core.manifest.yml` および `schema/*.cue` に定義されます。
   * 4リポジトリ構成、3つの標準鍵ロール（`ansible`、`user`、`git`）、セキュリティベースライン、CUE 検証ルールを規定します。
2. **Tier 2 (`site`)：サイト宣言意図**
   * `conf/openlab.manifest.yml` に保存されます。
   * クラスター名、ドメイン、Flat LAN サブネット（`192.168.1.0/24`）、ゲートウェイ、管理者/Ansible ユーザー、Gitea エンドポイントを保持します。`archinstall` と同様に `lab-init` で対話的に生成・エクスポートされます。
3. **Tier 3 (`node`)：動的マシンテレメトリ**
   * `conf/nodes/*.json`（インベントリ分類）と `node-information/node_<hostname>.json`（CMDB ハードウェア・コンテナ・鍵情報）に保存されます。
   * 静的マニフェストにはハードコードせず、`lab-node` と `lab-discover` で動的プローブし、`engine/classifier.py` が `ansible/inventory/hosts.yml` へコンパイルします。

## 2. 4リポジトリ連携とブラスト半径の隔離

CI/CD トークン侵害時の被害範囲（Blast Radius）を限定するため、下流リポジトリを 4 つに分離しています。

* **`openlab-operations`**：Ansible プレイブック、ロール、エンジン、CLI ツール。
* **`openlab-workflows`**：Gitea Actions ワークフロー。自動化トークン（`ci-bot`）の権限はここに限定され、`openlab-operations` のコード変更は**物理的に不可能**です。
* **`openlab-configs`**：ノードのハードウェア事実（`node-information/node_*.json`）、パッケージ一覧、自動生成された Markdown マニュアル。
* **`openlab-secrets`**：公開鍵、エンドポイント鍵レジストリ、暗号化シークレット。

## 3. Flat LAN とマルチディストリビューション Linux 対応

* **ネットワークスキーマ (`schema/network.cue`)**：標準的な単一サブネット（`192.168.1.0/24`）向けに設計され、サブネット重複や不正なゲートウェイ設定を CUE で防止します。
* **対応ディストリビューション**：**Arch Linux**、**Debian**、**Ubuntu**、**Oracle Linux**、**Alpine Linux**、**VMware Photon OS** および汎用 systemd Linux をネイティブサポートします。

## 4. ゼロ依存 Python エンジン

すべての CLI ツール（`bin/lab-*` / `tools/bin/lab-*`）は `tools/lib/core/` を共有し、100% Python 3 標準ライブラリで実装されています。管理対象ノードに Ansible をインストールする必要はなく、Gitea Act Runner コンテナが一元的に Ansible を実行します。
