# lab-INIT(1) - OpenLabOps Cluster Initialization Wizard

## NAME
`lab-init` - Day-0 Turnkey Cluster Initialization Wizard

## CATEGORY
> **[Installation & Initial Setup]**

## SYNOPSIS
```bash
./bin/lab-init [OPTIONS]
```

## DESCRIPTION
`lab-init` is the Day-0 turnkey onboarding commander for the OpenLabOps operations suite. It automates:
1. Interactive parameter gathering (Cluster name, domain, admin account, automation user, Gitea endpoint, Docker host).
2. Ephemeral bootstrap Ed25519 key generation in `/tmp/lab_bootstrap_keys/`.
3. Dynamic node onboarding and sensory probing without from-IP restrictions.
4. Network CIDR classification and automatic inventory compilation (`ansible/inventory/hosts.yml`).
5. Permanent key generation, from-IP white-listing injection (`from="192.168.1.0/24,..."`), verification, and purging of ephemeral keys (Zero Residual).
6. Automatic creation of the 5 downstream federation repositories on Gitea (`openlab-ansible`, `openlab-configs`, `openlab-secrets`, `openlab-tools`, `openlab-workflows`).

## OPTIONS
- `--lang <zh_TW|en_US|ja_JP>`  
  Pre-select UI and deployment locale (Traditional Chinese, English, Japanese). If omitted in interactive mode, a Step 0 language selection menu will be presented.
- `--manifest <PATH>`  
  Pre-seed initialization with a declarative Day-0 onboarding manifest (e.g. `tests/conf/openlab.manifest.test.yml`).
- `--legacy-key <PATH>`  
  Specify a legacy private key for mixed-scenario onboarding.
- `--non-interactive`  
  Run without interactive prompts, using defaults or values from manifest.
- `--with-gitea-runner`  
  Optionally provision and launch Gitea Act Runner container.
- `--with-remote-dev`  
  Optionally provision and launch AGY-Remote SRE development container.

## EXIT STATUS
- `0`: Initialization succeeded, all nodes operational and secured.
- `1`: Handover, verification, or preflight failure.

## EXAMPLES
```bash
# Interactive TUI mode (prompting for parameters):
./bin/lab-init

# Declarative batch execution with manifest:
./bin/lab-init --manifest tests/conf/openlab.manifest.test.yml --non-interactive
```

