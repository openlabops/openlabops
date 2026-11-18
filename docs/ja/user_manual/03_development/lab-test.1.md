# lab-TEST(1) - Sandbox Testing Engine

## NAME
`lab-test` - Multi-Distro Virtual Sandbox Fleet & Verification Engine

## カテゴリ (CATEGORY)
> **[開発・テスト・IaC メンテナンス (Development, Testing & IaC)]**

## SYNOPSIS
```bash
./bin/lab-test [OPTIONS]
```

## DESCRIPTION
`lab-test` provisions an isolated Docker testbed (`172.28.0.0/16`) containing 8 distinct nodes:
- `mock-console` (172.28.0.5) - Arch Linux operator workstation
- `mock-gitea` (172.28.0.2) - Local Gitea server
- `mock-arch` (172.28.0.10) - Arch Linux target node
- `mock-photon` (172.28.0.20) - VMware Photon OS target node
- `mock-oracle` (172.28.0.30) - Oracle Linux 9 target node
- `mock-debian` (172.28.0.40) - Debian 12 target node
- `mock-alpine` (172.28.0.50) - Alpine Linux target node
- `mock-appliance` (172.28.0.60) - Firmware/Storage appliance target node

## MODES OF OPERATION
1. **Automated End-to-End Pipeline (Default / `-a`)**:
   Spins up containers, synchronizes Gitea repository, runs Day-0 initialization with `tests/conf/openlab.manifest.test.yml`, verifies key rotation and tools deployment, and prints the operational dashboard.
2. **Full Sequential Pipeline (`-f, --full`)**:
   Runs standard automated sandbox tests, tears down, runs secondary test suite, and cleans up cleanly.
3. **Manual Interactive Mode (`-m, --manual`)**:
   Starts or ensures the sandbox fleet is running, keeps all containers online, and provides interactive prompts or `docker exec` commands for human exploration.
4. **Clean Teardown (`-d, --down, --clean`)**:
   Stops all running test containers and removes virtual bridge network (`172.28.0.0/16`).

## OPTIONS
- `-f, --full`               : Execute full dual automated verification suite.
- `-a, --auto`               : Run automated sandbox test pipeline.
- `-m, --manual`             : Interactive testing mode (preserves containers).
- `-s, --status, --info`     : Display active container fleet status and `docker exec` commands.
- `-r, --reset`              : Reset mock node authorization keys and test users to Day-0.
- `-d, --down, --clean`      : Stop and destroy all sandbox test containers.
- `-h, --help`               : Display help information.

## EXAMPLES
```bash
# Run one-command automated test and view dashboard:
./bin/lab-test

# Show running container commands:
./bin/lab-test -s

# Enter mock console interactively:
docker exec -it mock-console bash

# Destroy test environment:
./bin/lab-test -d
```

