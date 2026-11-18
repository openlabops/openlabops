# lab-DIFF(1) - Configuration Drift Detector

## NAME
`lab-diff` - Bidirectional IaC Drift Inspector & Template Diff Viewer

## カテゴリ (CATEGORY)
> **[開発・テスト・IaC メンテナンス (Development, Testing & IaC)]**

## SYNOPSIS
```bash
./bin/lab-diff [OPTIONS]
```

## DESCRIPTION
`lab-diff` inspects discrepancies between current declarative templates/manifests and rendered downstream repository states. It provides a visual networked diff of configuration drift without applying changes.

## OPTIONS
- `--manifest <PATH>`      : Path to site manifest (default: `conf/openlab.manifest.yml`).
- `--dest-prefix <PREFIX>` : Target downstream repo prefix to compare against.
- `--help, -h`             : Display usage summary.

## EXAMPLES
```bash
# Preview configuration drift against downstream repositories:
./bin/lab-diff

# Preview drift using a custom test manifest:
./bin/lab-diff --manifest tests/conf/openlab.manifest.test.yml
```

