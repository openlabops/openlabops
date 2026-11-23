---
id: architecture
title: システムアーキテクチャ
sidebar_position: 2
---

# システムアーキテクチャ

OpenLabOps は**ゼロ依存・宣言的 Homelab 運用フレームワーク（Operations Framework）**として設計されており、「不変フレームワーク契約」「サイト宣言意図」「ライブノードテレメトリ」を厳格に 3 層へ分離し、権限境界が分離された 4 つの下流 GitOps リポジトリへ展開します。

```mermaid
flowchart TB
    subgraph Console["管理ワークステーション (~/.ssh Agent)"]
        CLI["ゼロ依存 Python CLI<br/>lab-init / lab-node / lab-status / lab-tools"]
        T1["Tier 1: コア仕様<br/>conf/core.manifest.yml + schema/*.cue"]
        T2["Tier 2: サイト意図<br/>conf/openlab.manifest.yml"]
        T3["Tier 3: ノードテレメトリ<br/>conf/nodes/*.json"]
    end

    subgraph Federation["4リポジトリ GitOps 連携"]
        OPS["openlab-operations<br/>Playbooks + フレームワーク"]
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

## 1. リポジトリ構造

```text
openlabops/
├── bin/                        # コントロールプレーン入口 (lab-init, lab-node, lab-apply, lab-test)
├── engine/                     # Python コアフレームワーク (compiler, classifier, discover, initialize, onboard)
├── schema/                     # 不変 CUE 契約 (invariants, network, roles, keys, nodes)
├── conf/                       # SSOT マニフェストと動的ノード分類 (nodes/*.json)
├── ansible/                    # ステートレスなプレイブック、ロール、group_vars
├── tools/                      # ゼロ依存エンドポイント・運用 CLI (bin/lab-* & lib/core/*)
├── workflows/                  # Gitea Actions ワークフローとコンポジットアクション
├── templates/                  # 下流リポジトリ展開テンプレート (ansible, configs, workflows)
├── lang/                       # 多言語 i18n 辞書 (en_US.json, zh_TW.json, ja_JP.json)
└── tests/                      # ユニットテスト、Dagger DinD E2E、マルチディストリビューション Docker サンドボックス
```

## 2. 3層分離モデル

1. **Tier 1 (`core`)：不変フレームワーク仕様**
   * `conf/core.manifest.yml` および `schema/*.cue` に定義されます。
   * 4リポジトリ構成、3つの標準鍵ロール（`ansible`、`user`、`git`）、セキュリティベースライン、CUE 検証ルールを規定します。
2. **Tier 2 (`site`)：サイト宣言意図**
   * `conf/openlab.manifest.yml` に保存されます。
   * クラスター名、ドメイン、Flat LAN サブネット（`192.168.1.0/24`）、ゲートウェイ、管理者/Ansible ユーザー、Gitea エンドポイントを保持します。`archinstall` と同様に `lab-init` で対話的に生成・エクスポートされ、`--manifest` で無人再現できます。
3. **Tier 3 (`node`)：動的マシンテレメトリ**
   * **インベントリ分類 (`conf/nodes/*.json`)**：分類属性（`os_family`、`distribution`、`role`、`capabilities`）のみを保持し、ハードウェアテレメトリ（`mac_address`、`cpu_cores`、`memory_mb`）は一切混在させません。
   * **CMDB ハードウェアテレメトリ (`node-information/node_<hostname>.json`)**：`lab-discover`（`engine/bootstrap_probe.sh`）が独立してプローブし、RAM、CPU、ディスク、Docker コンテナ、待機ポート、`authorized_keys` フィンガープリントを記録します。
   * **動的コンパイル**：`engine/classifier.py` が純粋な Python 標準ライブラリで `conf/nodes/*.json` を `ansible/inventory/hosts.yml` へコンパイルします（実行時 CUE 依存ゼロ）。

## 3. 4リポジトリ連携とブラスト半径の隔離

| リポジトリ | 内容 | `ci-bot` 権限 |
| :--- | :--- | :--- |
| **`openlab-operations`** | Ansible プレイブック、ロール、フレームワーク、CLI ツール | **読み取り専用**（改変不可） |
| **`openlab-workflows`** | Gitea Actions ワークフロー＆コンポジットアクション | **読み取り / ディスパッチ** |
| **`openlab-configs`** | CMDB `node-information/node_*.json`、パッケージ一覧、Markdown マニュアル | **テレメトリ書き込み** |
| **`openlab-secrets`** | 公開鍵、エンドポイント鍵レジストリ、暗号化シークレット | **鍵ポリシー参照** |

## 4. ゼロ依存フレームワークと Gitea Act Runner 実行モデル

* **100% Python 標準ライブラリ (`[INV-01]`)**：組み込み `yaml_parser.py`、`urllib.request` ベースの `gitea_api.py`、`curses` ベースの `ui_curses.py` により外部依存ゼロで動作します。
* **エンドポイント Ansible レス設計**：管理対象ノードや端末には Python 3 と OpenSSH のみ必要です。Ansible プレイブックは **Gitea Act Runner** コンテナ（`ansible-core` 内蔵）上で一元実行されます。
* **Flat LAN とマルチディストリビューション対応**：`schema/network.cue` が Flat LAN（`192.168.1.0/24`）境界を強制し、**Arch Linux**、**Debian**、**Ubuntu**、**Oracle Linux**、**Alpine Linux**、**VMware Photon OS** をネイティブサポートします。
