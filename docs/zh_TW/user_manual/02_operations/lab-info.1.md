# lab-INFO(1) - Ground Truth Sensory Facts & Doc Generator

## NAME
`lab-info` - Ground Truth Sensory Fact Extraction & Markdown Doc Generator

## 類別 (CATEGORY)
> **[日常運維 App (Post-Installation Operational App)]**

## SYNOPSIS
```bash
lab-info [OPTIONS]
```

## DESCRIPTION
`lab-info` inspects machine telemetry from `conf/nodes/*.json` (and `node-information/`) and renders human-readable Markdown architecture documentation into `docs/`.

## OPTIONS
- `-a, --all`        : Re-render documentation for all managed nodes.
- `-d, --diff`       : Check for changes between telemetry and committed documentation.
- `-p, --packages`   : Include audited manual package list in rendered documentation.
- `-v, --verbose`    : Print detailed rendering logs.

## EXAMPLES
```bash
# Generate documentation for all nodes:
lab-info -a
```

