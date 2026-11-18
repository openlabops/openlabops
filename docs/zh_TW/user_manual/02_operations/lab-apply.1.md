# lab-APPLY(1) - Manifest Compiler & Code Synchronizer

## NAME
`lab-apply` - Template Compiler & Downstream Federation Code Synchronizer

## 類別 (CATEGORY)
> **[開發、測試與 IaC 維護 (Development, Testing & IaC)]**

## SYNOPSIS
```bash
./bin/lab-apply [OPTIONS]
```

## DESCRIPTION
`lab-apply` renders parameterized templates (Ansible inventory, vars, Gitea actions workflows) based on site intent (`conf/openlab.manifest.yml`), and synchronizes non-template core code into downstream federation repositories (`openlab-ansible`, `openlab-configs`, `openlab-tools`, `openlab-workflows`).

## OPTIONS
- `--manifest <PATH>`      : Path to site manifest (default: `conf/openlab.manifest.yml`).
- `--dest-prefix <PREFIX>` : Target downstream repo prefix (default: `openlab-`).
- `--apply`                : Write rendered files and apply synchronization (dry-run if omitted).
- `--full-federation`      : Perform complete core code synchronization to all 5 repos.
- `--ops-internal`         : Also apply rendered templates to internal `openlabops` paths.
- `--distill-openlab`      : Distill `openlabops` into `openlabops` open-source hub.

## EXAMPLES
```bash
# Dry-run preview of template rendering:
./bin/lab-apply

# Apply rendered files to internal openlabops paths:
./bin/lab-apply --ops-internal --apply

# Distill into openlabops:
./bin/lab-apply --distill-openlab --apply
```

