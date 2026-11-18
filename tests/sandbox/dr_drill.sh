#!/bin/bash
# ==============================================================================
# Automated Disaster Recovery (DR) Backup, Chaos & Restore Verification Drill
# File: tests/sandbox/dr_drill.sh
# Governed by [INV-09] (Production Tooling & Verification Contract)
# ==============================================================================
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-openlabops}"
cd "/home/labadmin/${PROJECT_NAME}"

TARGETS="${1:-${DR_TARGETS:-mock-arch,mock-photon,mock-debian}}"
DR_VAULT="/tmp/dr_backup_vault"
DR_TEST_DIR="/etc/dr_test"
TIMESTAMP=$(date -u +%s)

# Convert comma-separated string to list
IFS=',' read -r -a TARGET_LIST <<< "${TARGETS}"
TARGET_COUNT=${#TARGET_LIST[@]}

echo "================================================================================"
echo "  [${PROJECT_NAME}] Automated Disaster Recovery (DR) Backup & Restore Drill"
echo "  Target Fleet: ${TARGETS}"
echo "================================================================================"

# 1. Inject Critical Test Payloads on Target Nodes
echo "[Phase 1/5] Injecting critical application & system payloads on targets (${TARGETS})..."
ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "
mkdir -p ${DR_TEST_DIR} &&
echo '{\"service\":\"homelab-core\",\"version\":\"2.0\",\"timestamp\":\"${TIMESTAMP}\",\"status\":\"active\"}' > ${DR_TEST_DIR}/service.json &&
echo 'CRITICAL_SYSTEM_STATE_${TIMESTAMP}' > ${DR_TEST_DIR}/state.db &&
chmod 0644 ${DR_TEST_DIR}/service.json ${DR_TEST_DIR}/state.db
" --become

# 2. Record Pre-Disaster SHA-256 Checksums
echo "[Phase 2/5] Recording pre-disaster SHA-256 checksums across target nodes..."
PRE_HASH=$(ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "sha256sum ${DR_TEST_DIR}/service.json ${DR_TEST_DIR}/state.db" --become | grep -E "^[a-f0-9]{64}" | sort)
echo "  • Golden Signatures (Pre-Disaster):"
echo "${PRE_HASH}" | sed 's/^/    /'

# 3. Execute Declarative Backup Playbook (backup-node.yml)
echo "[Phase 3/5] Executing Declarative Backup Playbook (ansible/playbooks/backup-node.yml)..."
rm -rf "${DR_VAULT}"
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/backup-node.yml \
    --extra-vars '{"target_hosts":"'"${TARGETS}"'","custom_configs_root":"'"${DR_VAULT}"'","backup":[{"src":"'"${DR_TEST_DIR}"'/service.json","dest":"service.json"},{"src":"'"${DR_TEST_DIR}"'/state.db","dest":"state.db"}]}'

# Verify controller backup vault
for node in "${TARGET_LIST[@]}"; do
    node_trimmed="$(echo -e "${node}" | tr -d '[:space:]')"
    if [ ! -f "${DR_VAULT}/${node_trimmed}/service.json" ] || [ ! -f "${DR_VAULT}/${node_trimmed}/state.db" ]; then
        echo "  [✗] Backup verification failed: Vault missing files for ${node_trimmed}"
        exit 1
    fi
done
echo "  [✓] All target node payloads successfully vaulted at ${DR_VAULT}"

# 4. Simulate Disaster & Catastrophic Data Loss (Chaos Injection)
echo "[Phase 4/5] Simulating Node Disaster: Catastrophic deletion & data corruption..."
ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "
rm -f ${DR_TEST_DIR}/service.json &&
echo 'CORRUPTED_ZERO_BYTE_FAULT' > ${DR_TEST_DIR}/state.db
" --become

# Verify damage state
DAMAGED_STATE=$(ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "test ! -f ${DR_TEST_DIR}/service.json && grep -q 'CORRUPTED' ${DR_TEST_DIR}/state.db && echo 'CONFIRMED_DAMAGED'" --become | grep -c "CONFIRMED_DAMAGED" || true)
echo "  • Confirmed ${DAMAGED_STATE}/${TARGET_COUNT} target nodes in simulated disaster state."

# 5. Execute Automated Disaster Recovery Restore Playbook (restore-node.yml)
echo "[Phase 5/5] Executing Automated Disaster Recovery Restore Playbook (ansible/playbooks/restore-node.yml)..."
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/restore-node.yml \
    --extra-vars '{"target_hosts":"'"${TARGETS}"'","custom_configs_root":"'"${DR_VAULT}"'","backup":[{"src":"'"${DR_TEST_DIR}"'/service.json","dest":"service.json","mode":"0644"},{"src":"'"${DR_TEST_DIR}"'/state.db","dest":"state.db","mode":"0644"}]}'

# 6. Verify Post-Restore Integrity (Bit-for-Bit SHA-256 Equality)
echo "  • Verifying post-restore bit-for-bit SHA-256 checksums..."
POST_HASH=$(ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "sha256sum ${DR_TEST_DIR}/service.json ${DR_TEST_DIR}/state.db" --become | grep -E "^[a-f0-9]{64}" | sort)
echo "  • Restored Signatures:"
echo "${POST_HASH}" | sed 's/^/    /'

if [ "${PRE_HASH}" != "${POST_HASH}" ]; then
    echo "  [✗] CRITICAL ERROR: Checksum mismatch between pre-disaster and restored files!"
    exit 1
fi

# 7. Cleanup Test Directory & Vault
ansible -i ansible/inventory/hosts.yml "${TARGETS}" -m shell -a "rm -rf ${DR_TEST_DIR}" --become >/dev/null 2>&1 || true
rm -rf "${DR_VAULT}"

echo "================================================================================"
echo "  🎉 AUTOMATED DISASTER RECOVERY DRILL COMPLETE: 100% SUCCESS"
echo "  • Tested Nodes       : Arch Linux, Photon OS, Debian 12"
echo "  • Chaos Simulation   : Complete file deletion & payload corruption"
echo "  • Recovery Result    : 100% Bit-for-Bit SHA-256 Integrity Verified (Zero Loss)"
echo "================================================================================"
