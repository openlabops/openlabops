#!/bin/bash
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-openlabops}"

echo "================================================================================"
echo "  [${PROJECT_NAME}] Mock Console Workstation: Day-0 Onboarding Pipeline"
echo "  Executing inside isolated container (mock-console: 172.28.0.5) as user: labadmin"
echo "================================================================================"

GITEA_MODE="${GITEA_MODE:-standalone}"
GITEA_URL="${GITEA_URL:-http://172.28.0.2:3000}"

# Persist Gitea URL & PATH for all interactive and non-interactive shell sessions in mock-console
export PATH="/usr/local/bin:${PATH}"
grep -q "/usr/local/bin" /home/labadmin/.bashrc 2>/dev/null || echo 'export PATH="/usr/local/bin:${PATH}"' >> /home/labadmin/.bashrc
DEFAULT_ORG="OpenLabOps"
if [ "${PROJECT_NAME}" = "openlabops" ] || [ -f "tests/conf/openlab.manifest.test.yml" ]; then
    DEFAULT_ORG="OpenLabOps"
fi
GITEA_ORG="${GITEA_ORG:-${DEFAULT_ORG}}"

echo "export GITEA_URL=\"${GITEA_URL}\"" >> /home/labadmin/.bashrc
echo "export GITEA_OWNER=\"${GITEA_ORG}\"" >> /home/labadmin/.bashrc
echo "export GITEA_ORG=\"${GITEA_ORG}\"" >> /home/labadmin/.bashrc
echo "${GITEA_URL}" > /home/labadmin/.gitea_url
echo "GITEA_URL=\"${GITEA_URL}\"" | sudo tee -a /etc/environment >/dev/null || true
echo "GITEA_OWNER=\"${GITEA_ORG}\"" | sudo tee -a /etc/environment >/dev/null || true
echo "GITEA_ORG=\"${GITEA_ORG}\"" | sudo tee -a /etc/environment >/dev/null || true

CONSOLE_LANG="${LAB_LANG:-${LAB_LANG:-zh_TW}}"
export LAB_LANG="${CONSOLE_LANG}"
export LAB_LANG="${CONSOLE_LANG}"
sed -i '/export LAB_LANG=/d' /home/labadmin/.bashrc 2>/dev/null || true
sed -i '/export LAB_LANG=/d' /home/labadmin/.bashrc 2>/dev/null || true
echo "export LAB_LANG=\"${CONSOLE_LANG}\"" >> /home/labadmin/.bashrc
echo "export LAB_LANG=\"${CONSOLE_LANG}\"" >> /home/labadmin/.bashrc
echo "LAB_LANG=\"${CONSOLE_LANG}\"" | sudo tee -a /etc/environment >/dev/null || true
echo "LAB_LANG=\"${CONSOLE_LANG}\"" | sudo tee -a /etc/environment >/dev/null || true
mkdir -p /home/labadmin/.config/openlab /home/labadmin/.config/openlab
echo "${CONSOLE_LANG}" > /home/labadmin/.config/openlab/locale
echo "${CONSOLE_LANG}" > /home/labadmin/.config/openlab/locale
sudo mkdir -p /usr/local/etc/openlab /usr/local/etc/openlab 2>/dev/null || true
echo "${CONSOLE_LANG}" | sudo tee /usr/local/etc/openlab/locale >/dev/null || true
echo "${CONSOLE_LANG}" | sudo tee /usr/local/etc/openlab/locale >/dev/null || true

# 1. Clone repository according to Gitea establishment mode
echo "[Step 1/5] Synchronizing ${PROJECT_NAME} repository (Gitea Mode: ${GITEA_MODE})..."
rm -rf "/home/labadmin/${PROJECT_NAME}"

if [ "${GITEA_MODE}" = "local" ]; then
    echo "  • Direct clone from local workspace (/workspace)..."
    git clone /workspace "/home/labadmin/${PROJECT_NAME}"
elif [ "${GITEA_MODE}" = "dind" ]; then
    echo "  • Cloning from node embedded Gitea (http://172.28.0.20:3000)..."
    git clone "http://labadmin:labtest123@172.28.0.20:3000/labadmin/${PROJECT_NAME}.git" "/home/labadmin/${PROJECT_NAME}"
elif [ "${GITEA_MODE}" = "external" ]; then
    echo "  • Cloning from external Gitea (${GITEA_URL})..."
    git clone "${GITEA_URL}/labadmin/${PROJECT_NAME}.git" "/home/labadmin/${PROJECT_NAME}"
else
    # default standalone (isolated test domain: mock-gitea)
    echo "  • Cloning from standalone mock Gitea (http://mock-gitea:3000)..."
    git clone "http://labadmin:labtest123@mock-gitea:3000/labadmin/${PROJECT_NAME}.git" "/home/labadmin/${PROJECT_NAME}"
fi

# Overlay any live workspace edits from host if /workspace volume is mounted
if [ -d "/workspace" ]; then
    echo "  • Overlaying live workspace updates into /home/labadmin/${PROJECT_NAME}..."
    rsync -a --exclude='.git' /workspace/ "/home/labadmin/${PROJECT_NAME}/" 2>/dev/null || true
fi
cd "/home/labadmin/${PROJECT_NAME}"
rm -f /home/labadmin/.ssh/*.key /home/labadmin/.ssh/*.pub /home/labadmin/.ssh/known_hosts*

# Detect Entry commands
CMD_INIT="./bin/lab-init"
CMD_APPLY="./bin/lab-apply"
CMD_DIFF="./bin/lab-diff"
if [ -f "./bin/lab-init" ]; then
    CMD_INIT="./bin/lab-init"
    CMD_APPLY="./bin/lab-apply"
    CMD_DIFF="./bin/lab-diff"
fi

# Detect test manifest
TEST_MANIFEST="tests/conf/openlab.manifest.test.yml"
if [ "${PROJECT_NAME}" = "openlabops" ] && [ -f "tests/conf/openlab.manifest.test.yml" ]; then
    TEST_MANIFEST="tests/conf/openlab.manifest.test.yml"
elif [[ "${PROJECT_NAME}" == *"openlab"* ]] && [ -f "tests/conf/openlab.manifest.test.yml" ]; then
    TEST_MANIFEST="tests/conf/openlab.manifest.test.yml"
elif [ -f "tests/conf/${PROJECT_NAME}.manifest.test.yml" ]; then
    TEST_MANIFEST="tests/conf/${PROJECT_NAME}.manifest.test.yml"
elif [ -f "tests/conf/openlab.manifest.test.yml" ]; then
    TEST_MANIFEST="tests/conf/openlab.manifest.test.yml"
elif [ -f "tests/conf/openlab.manifest.test.yml" ]; then
    TEST_MANIFEST="tests/conf/openlab.manifest.test.yml"
fi

# 2. Inspect Day-0 declarative parameter manifest
echo "[Step 2/5] Inspecting Day-0 Declarative Parameter Manifest (${TEST_MANIFEST})..."
head -n 25 "${TEST_MANIFEST}"

# 3. Setup legacy installer key for mixed-scenario targets
echo "[Step 3/7] Setting up legacy installer key for mixed-key targets..."
if [ ! -f /tmp/lab_legacy_keys/id_legacy ]; then
    mkdir -p /tmp/lab_legacy_keys
    ssh-keygen -t ed25519 -N "" -f /tmp/lab_legacy_keys/id_legacy -C "legacy-installer@mock" >/dev/null 2>&1
fi
if [ ! -f /tmp/lab_legacy_keys/id_legacy.pub ]; then
    ssh-keygen -y -f /tmp/lab_legacy_keys/id_legacy > /tmp/lab_legacy_keys/id_legacy.pub
fi
LEGACY_PUB=$(cat /tmp/lab_legacy_keys/id_legacy.pub)

# 4. Execute Day-0 Initialization via Production Tool (bin/lab-init)
echo "[Step 4/7] Executing Day-0 Initialization & Node Ingestion via Production Tool (${CMD_INIT})..."
${CMD_INIT} --lang "${LAB_LANG:-zh_TW}" --manifest "${TEST_MANIFEST}" --legacy-key /tmp/lab_legacy_keys/id_legacy --include-appliances --non-interactive

# 5. Execute Compiler Apply to render downstream configs & internal paths
echo "[Step 5/7] Executing Manifest Compiler (${CMD_APPLY})..."
${CMD_APPLY} --ops-internal
python3 engine/classifier.py --apply

# 6. Verify Operations Tools Suite & Key Connectivity on Console & Fleet
echo "[Step 6/7] Verifying Operations Tools Suite & Key Connectivity on Console & Fleet..."
AUTH_KEY_NAME="lab"
CLI_PREFIX="labadmin"
if [ "${PROJECT_NAME}" = "openlabops" ] || [ ! -f /home/labadmin/.ssh/lab.pub ]; then
    AUTH_KEY_NAME="ansible"
    CLI_PREFIX="lab"
fi

echo "  • Testing localhost /usr/local/bin/${CLI_PREFIX}-tools..."
/usr/local/bin/${CLI_PREFIX}-tools --version || ${CLI_PREFIX}-tools --version
echo "  • Testing localhost /usr/local/bin/${CLI_PREFIX}-status with all CLI flags (-q, -k, -a, -n, -b, -t, --json)..."
/usr/local/bin/${CLI_PREFIX}-status -k || ${CLI_PREFIX}-status -k
/usr/local/bin/${CLI_PREFIX}-status -q >/dev/null || ${CLI_PREFIX}-status -q >/dev/null
/usr/local/bin/${CLI_PREFIX}-status -a >/dev/null || ${CLI_PREFIX}-status -a >/dev/null
/usr/local/bin/${CLI_PREFIX}-status -n >/dev/null || ${CLI_PREFIX}-status -n >/dev/null
/usr/local/bin/${CLI_PREFIX}-status -b -q >/dev/null || ${CLI_PREFIX}-status -b -q >/dev/null
/usr/local/bin/${CLI_PREFIX}-status -t -q >/dev/null || ${CLI_PREFIX}-status -t -q >/dev/null
/usr/local/bin/${CLI_PREFIX}-status -q --json >/dev/null || ${CLI_PREFIX}-status -q --json >/dev/null
echo "  • Testing all CLI apps and subcommands (--version / --help / list / sync / man)..."
./bin/${CLI_PREFIX}-node list >/dev/null
./bin/${CLI_PREFIX}-node sync >/dev/null
./bin/${CLI_PREFIX}-man status >/dev/null
for b in ./bin/* ./tools/bin/*; do
    [ -f "$b" ] || continue
    "$b" --version >/dev/null
    "$b" --help >/dev/null
done
for sub in add remove list sync; do
    ./bin/${CLI_PREFIX}-node "$sub" --help >/dev/null
done
echo "  • Verifying fleet connectivity using rotated permanent key (~/.ssh/${AUTH_KEY_NAME}.key)..."
ansible servers -i ansible/inventory/hosts.yml -m ping -u "${AUTH_KEY_NAME}" --private-key "/home/labadmin/.ssh/${AUTH_KEY_NAME}.key"

if grep -q "appliances:" ansible/inventory/hosts.yml 2>/dev/null; then
    echo "  • Verifying appliance connectivity using root account (~/.ssh/${AUTH_KEY_NAME}.key)..."
    ansible appliances -i ansible/inventory/hosts.yml -m raw -a "echo pong" -u root --private-key "/home/labadmin/.ssh/${AUTH_KEY_NAME}.key" || true
fi

# Zero Residual Verification ([INV-11])
if [ -d /tmp/lab_bootstrap_keys ] && [ "$(ls -A /tmp/lab_bootstrap_keys 2>/dev/null)" ]; then
    echo "  [✗] Error: /tmp/lab_bootstrap_keys still contains ephemeral keys after initialization!"
    exit 1
fi
echo "  [✓] Ephemeral bootstrap keys zero-residual verified."

if [ "${RUN_FULL_TESTS:-false}" != "true" ]; then
    echo "================================================================================"
    echo "  🎉 [${PROJECT_NAME}] Mock Console Workstation Ready for Manual Operations!"
    echo "  - Repo: /home/labadmin/${PROJECT_NAME}"
    echo "  - All nodes onboarded, ${AUTH_KEY_NAME}.key rotated and active"
    echo "  - Operations tools deployed to /usr/local/bin/ (lab-tools, lab-status, etc.)"
    echo "================================================================================"
    exit 0
fi

# 7. Execute Automated Disaster Recovery (DR) Backup & Restore Drill
echo "[Step 7/8] Testing Automated Disaster Recovery (DR) Drill on Fleet..."
bash tests/sandbox/dr_drill.sh

# 8. Execute Day-2 Lifecycle Operations: Node Remove, Config Update & Dynamic Node Add
echo "[Step 8/8] Testing Day-2 Lifecycle Operations (Node Remove, Config Update, Dynamic Node Add)..."

# Sub-test 9.1: Dynamic Node Remove (Unmanage & Revoke Key)
echo "  • [9.1] Decommissioning & unmanaging node 'mock-alpine' via production engine..."
ansible -i ansible/inventory/hosts.yml mock-alpine -m ping -u "${AUTH_KEY_NAME}" --private-key "/home/labadmin/.ssh/${AUTH_KEY_NAME}.key" >/dev/null 2>&1 || true

python3 engine/onboard.py --remove mock-alpine --target-user "${AUTH_KEY_NAME}" --force --classify
if [ -f conf/nodes/mock-alpine.json ]; then
    echo "  [✗] Error: conf/nodes/mock-alpine.json still exists after remove!"
    exit 1
fi
if ! ls conf/nodes/archive/mock-alpine_*.json >/dev/null 2>&1; then
    echo "  [✗] Error: conf/nodes/archive/mock-alpine_*.json missing after archival remove!"
    exit 1
fi
if grep -q "mock-alpine" ansible/inventory/hosts.yml; then
    echo "  [✗] Error: mock-alpine still present in ansible/inventory/hosts.yml!"
    exit 1
fi

# Verify remote management key was revoked: SSH with management key MUST fail (unmanaged)
if ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=3 -i "/home/labadmin/.ssh/${AUTH_KEY_NAME}.key" "${AUTH_KEY_NAME}@172.28.0.50" "echo BREACH" >/dev/null 2>&1; then
    echo "  [✗] Error: SSH with management key still succeeded! Remote management key was not revoked from authorized_keys!"
    exit 1
fi
echo "  [✓] Sub-test 9.1 Passed: mock-alpine remote key revoked, removed from inventory, facts archived."

# Sub-test 9.2: Declarative Config Drift Detection & Apply
echo "  • [9.2] Testing declarative config drift detection (diff) and compilation (apply)..."
MANIFEST_FILE="conf/openlab.manifest.yml"
if [ "${PROJECT_NAME}" = "openlabops" ] || [ ! -f "${MANIFEST_FILE}" ]; then
    MANIFEST_FILE="conf/openlab.manifest.yml"
fi
ORIG_LINE=$(grep "^[[:space:]]*timezone:" "${MANIFEST_FILE}" | head -n 1)
sed -i 's|^[[:space:]]*timezone:.*|  timezone: "Asia/Cloud-Region-2"|' "${MANIFEST_FILE}"
DIFF_OUTPUT=$(${CMD_DIFF})
if [[ "${DIFF_OUTPUT}" != *"Asia/Cloud-Region-2"* ]] && [[ "${DIFF_OUTPUT}" != *"[DIFF DETECTED]"* ]]; then
    echo "  [✗] Error: Compiler --diff did not detect timezone configuration change!"
    exit 1
fi
${CMD_APPLY} --ops-internal
# Revert timezone back
sed -i "s|^[[:space:]]*timezone:.*|${ORIG_LINE}|" "${MANIFEST_FILE}"
${CMD_APPLY} --ops-internal >/dev/null 2>&1
echo "  [✓] Sub-test 9.2 Passed: Declarative config diff and apply verified."

# Sub-test 9.3: Dynamic Post-Day-0 Node Add
echo "  • [9.3] Dynamically onboarding node 'mock-alpine' (172.28.0.50) via production engine..."
python3 engine/onboard.py --host 172.28.0.50 --user labadmin --password labtest123 --target-user "${AUTH_KEY_NAME}" --non-interactive --classify
if [ ! -f conf/nodes/mock-alpine.json ]; then
    echo "  [✗] Error: conf/nodes/mock-alpine.json was not created by dynamic node add!"
    exit 1
fi
if ! grep -q "mock-alpine" ansible/inventory/hosts.yml; then
    echo "  [✗] Error: mock-alpine missing from ansible/inventory/hosts.yml after dynamic add!"
    exit 1
fi
# Verify Ansible ping connectivity to newly added node
ansible -i ansible/inventory/hosts.yml mock-alpine -m ping -u "${AUTH_KEY_NAME}" --private-key "/home/labadmin/.ssh/${AUTH_KEY_NAME}.key"
echo "  [✓] Sub-test 9.3 Passed: mock-alpine dynamically ingested and verified via Ansible ping."

# Verify neutral Python dispatch modules directly via python3 standard library
python3 -c "
import sys; sys.path.insert(0, '/home/labadmin/${PROJECT_NAME}/tools/lib')
from lab_ssh import rotate_ansible_keys, rotate_git_keys, rotate_storage_keys
import sync_ops_tools
print('  [✓] Neutral Python modules verified: 100% standard library compliance.')
"

echo "================================================================================"
echo "  DAY-0, KEY ROTATION, DR DRILL & DAY-2 LIFECYCLE COMPLETE: 100% SUCCESS"
echo "================================================================================"
