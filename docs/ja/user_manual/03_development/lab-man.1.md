# lab-MAN(1) - Interactive Terminal User Manual Browser

## NAME
`lab-man` - Terminal Interactive User Manual & Reference Documentation Browser

## カテゴリ (CATEGORY)
> **[開発・テスト・IaC メンテナンス (Development, Testing & IaC)]**

## SYNOPSIS
```bash
./bin/lab-man [COMMAND_NAME]
```

## DESCRIPTION
`lab-man` provides a zero-dependency, terminal-native interactive manual browser for all OpenLabOps Operations Engine commands and tools. It scans `docs/user_manual/` across categorized sections (Installation, Operations, Development), renders high-readability ANSI-styled markdown in the terminal, and integrates seamlessly with `less` pager.

## MODES OF OPERATION

### 1. Interactive Classification Menu (Default)
When executed without arguments (`./bin/lab-man`), it launches a categorized terminal interface:
- **01_installation**: Day-0 cluster initialization (`lab-init`), dynamic node onboarding (`lab-node`), and telemetry probe (`lab-discover`).
- **02_operations**: Cluster health status (`lab-status`), SSH dispatcher & key rotation (`lab-ssh`), declarative backup (`lab-backup`), dotfiles manager (`lab-config`), multi-node upgrade (`lab-upgrade`), markdown documentation generator (`lab-info`), interactive TUI (`lab-tools`), template compiler (`lab-apply`), and drift inspector (`lab-diff`).
- **03_development**: Developer onboarding (`lab-dev-setup`), sandbox fleet verification (`lab-test`), and manual browser (`lab-man`).

### 2. Direct Command Lookup
When executed with a command name argument, it immediately opens the manual for that specific tool:
```bash
# Query lab-status manual directly
./bin/lab-man status

# Query lab-test manual directly
./bin/lab-man lab-test
```

## ENVIRONMENT & COMPLIANCE
- **100% Python Standard Library ([INV-01])**: Zero external dependencies, pure terminal ANSI sequences.
- **Automatic Pager Detection**: Automatically pipes output through `less -R` when standard output is an interactive TTY, falling back to clean text printing in non-interactive pipelines.

