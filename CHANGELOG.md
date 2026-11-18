# Changelog

All notable changes to OpenLabOps will be documented in this file.

## [1.0.0] - 2026-11-17

### Changed
- Aligned `scripts/install.sh` with the system-wide installation specification (`/usr/local/bin/openlab` + `/usr/local/bin/` symlinks) and strict root/sudo privilege enforcement
- Updated version SSOT (`VERSION`, `tools/VERSION`, `FALLBACK_VERSION`) to `1.0.0`
- Replaced `StrictHostKeyChecking=no` with `StrictHostKeyChecking=accept-new` in GitHub audit probe and Git key rotation workflow templates
- Updated `bin/lab-test --kvm` stub to exit non-zero with an explicit unsupported notice instead of silently succeeding
- Masked `ci-bot` token in `engine/initialize.py` terminal output and aligned storage path display to `/usr/local/bin/openlab/.gitea_token (mode 0600)`
- Enforced non-zero exit (`2`) on unknown commands/flags in `lab-tools`

### Added
- Standardized `-v` / `--version` and `prog` CLI metadata across all `bin/*` and `tools/bin/*` entrypoints
- Full i18n coverage (`en_US` default, `zh_TW`, `ja_JP`) for `lab-node`, `lab-boot-sync`, `lab-man`, and `lab-test`
- SemVer pre-release parsing and unit tests in `tools/lib/core/version.py` and `tests/unit/test_core_units.py`
- CUE schema validation and CLI `--version` / `--help` smoke checks in `.github/workflows/ci.yml`

### Fixed
- Fixed remote version lookup in `tools/lib/core/version.py` to probe both `openlab-operations` and `openlabops`
- Added SHA256 verification for `act_runner` binary and non-root `runner` user (`0750` permissions) in `extensions/containers/gitea-runner/Dockerfile`
- Fixed 84 broken relative links in `docs/zh_TW/`
- Deduplicated token lookup and install path logic in `ansible/scripts/post-push-trigger.sh` and `tools/lib/sync_ops_tools.py`

## [0.4.0] - 2026-11-16

### Added
- Zero-dependency Python standard library CLI toolchain (`bin/lab-*` & `tools/bin/lab-*`)
- Flat LAN (`192.168.1.0/24` example) schema validation via CUE (`schema/*.cue`)
- Three-tier manifest & node telemetry architecture (`conf/core.manifest.yml`, `conf/openlab.manifest.yml`, `conf/nodes/*.json`)
- Boot-time key sync service (`lab-boot-sync`) and lockout guard (`tools/lib/core/lockout.py`)
- Internationalization dictionaries (`lang/en_US.json`, `lang/zh_TW.json`, `lang/ja_JP.json`) with `en_US` as default locale
- GitHub Actions CI workflow (`.github/workflows/ci.yml`)

### Fixed
- Default locale aligned to `en_US` for OpenLabOps (`tools/lib/core/i18n.py`, `engine/initialize.py`, `tools/conf/tools.config.json`)
- Deduplicated repeated placeholder CIDRs across playbooks and documentation
- Fixed `lab-man` manual directory fallback resolution
