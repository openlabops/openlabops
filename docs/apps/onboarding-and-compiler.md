---
id: onboarding-and-compiler
title: Onboarding, Inventory & Compiler
sidebar_position: 1
---

# Onboarding, Inventory & Compiler CLI

These commands live in `bin/` and power Day-0 cluster bootstrap, dynamic node onboarding, hardware discovery, manifest compilation, and sandbox testing.

---

## `lab-init`

**Engine:** `engine/initialize.py`

Interactive Day-0 initialization commander. Like `archinstall`, it collects site intent interactively (or reads a saved manifest for unattended setup), generates permanent management keys, bootstraps the Gitea 4-repo federation and Act Runner, and exports `conf/openlab.manifest.yml`.

```bash
lab-init [--lang {zh_TW,en_US,ja_JP}] [--manifest FILE] [--non-interactive]
         [--with-gitea-runner] [--with-remote-dev] [--skip-nodes HOSTS]
```

* `--lang`: Set wizard and deployed cluster locale (`en_US`, `zh_TW`, `ja_JP`).
* `--manifest`: Unattended Day-0 onboarding from an exported manifest YAML.
* `--legacy-key`: Legacy SSH private key path for mixed-scenario initial onboarding.
* `--with-gitea-runner`: Configure and build the Gitea Act Runner container (with `ansible-core`).
* `--with-remote-dev`: Provision remote development container.
* `--skip-nodes`: Comma-separated hostnames to skip during onboarding.

---

## `lab-node`

**Engine:** `tools/lib/lab_node.py` (`bin/lab-node` -> `tools/bin/lab-node`)

Dynamic node ingestion and inventory management. Stores classification facts in `conf/nodes/<hostname>.json` (never hardware telemetry) and compiles `ansible/inventory/hosts.yml`.

```bash
lab-node {add,remove,list,sync}
```

* **`add <IP/Host> [--user USER]`**: Probes the target over SSH, detects OS family/distribution/role, writes `conf/nodes/<hostname>.json`, and recompiles inventory.
* **`remove <hostname>`**: Decommissions a node and purges it from `conf/nodes/` and inventory snapshots.
* **`list`**: Displays all currently managed nodes and their classifications.
* **`sync`**: Re-syncs and recalculates node snapshots against live facts.

---

## `lab-discover`

**Engine:** `engine/discover.py`

Sensory ground-truth hardware and service fact harvester. Strictly decoupled from `lab-node`.

```bash
lab-discover [--out-dir DIR] [--node HOST] [--manifest FILE]
```

* Executes lightweight native probes (`engine/bootstrap_probe.sh`) over SSH to collect RAM, CPU, disks, containers, listening ports, and `authorized_keys` fingerprints into `node-information/node_<hostname>.json`.

---

## `lab-diff` & `lab-apply`

**Engine:** `engine/compiler.py`

Declarative manifest compiler and federation synchronizer.

```bash
lab-diff [--manifest FILE] [--site SITE]
lab-apply --apply [--manifest FILE] [--dest-prefix PREFIX] [--base-dir DIR] [--create-dest-dirs]
```

* **`lab-diff`**: Compares rendered templates against current downstream federation repositories without writing changes.
* **`lab-apply`**: Renders `group_vars`, workflows, and site overlays and synchronizes them to downstream repositories (`<prefix>-operations`, `<prefix>-workflows`, `<prefix>-configs`, `<prefix>-secrets`).

---

## `lab-dev-setup`

**Script:** `bin/lab-dev-setup`

Declarative workstation bootstrapper invoking `ansible/playbooks/dev-environment.yml`. Ensures `ansible`, `cue`, and `docker` are ready; if `ansible` is missing, automatically creates `.venv` and installs `ansible-core`.

```bash
lab-dev-setup [--check | -c] [--force | -f]
```

---

## `lab-test`

**Script:** `bin/lab-test`

Unified sandbox & acceptance test orchestrator.

```bash
lab-test [-m | --manual] [-a | --auto] [-g | --dagger] [--dr [TARGET]]
         [--kvm [PERSONA]] [-s | --status] [-r | --reset] [-d | --down]
         [-G {standalone,dind,external,local}] [--lang {zh_TW,en_US,ja_JP}]
```

* `--manual`: Starts `mock-console`, `mock-gitea`, and multi-distro containers, then attaches an interactive shell inside `mock-console`.
* `--auto`: Full unattended E2E acceptance (boot -> onboard -> tool checks -> DR drill -> teardown).
* `--dagger`: Executes the Dagger DinD verification pipeline (`tests/e2e/test_dagger.py`).
* `--dr [target]`: Runs the SHA-256 disaster recovery drill (`tests/sandbox/dr_drill.sh`).
