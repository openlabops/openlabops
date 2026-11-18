#!/usr/bin/env bash
# ==============================================================================
# OpenLabOps Zero-Dependency Fast Installer
# Governed by [INV-01] (Zero External Dependencies) & [INV-02] (Zero Secrets in Repo)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/openlabops/openlabops/main/scripts/install.sh | bash
# ==============================================================================
set -euo pipefail

C_RESET="\033[0m"
C_BOLD="\033[1m"
C_GREEN="\033[32m"
C_CYAN="\033[36m"
C_YELLOW="\033[33m"
C_RED="\033[31m"

INSTALL_DIR="${OPENLAB_HOME:-/usr/local/bin/openlab}"
REPO_URL="${OPENLAB_REPO_URL:-https://github.com/openlabops/openlabops.git}"
BIN_DIR="/usr/local/bin"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo -e "${C_RED}[✗] Error: Root or sudo privileges are required to install OpenLabOps into ${INSTALL_DIR} and ${BIN_DIR}.${C_RESET}"
        echo -e "${C_RED}    Aborting installation.${C_RESET}"
        exit 1
    fi
    if [ -t 0 ]; then
        if ! sudo -v; then
            echo -e "${C_RED}[✗] Error: Unable to obtain sudo privileges. Aborting installation.${C_RESET}"
            exit 1
        fi
    elif [ -e /dev/tty ]; then
        if ! sudo -v </dev/tty; then
            echo -e "${C_RED}[✗] Error: Unable to obtain sudo privileges. Aborting installation.${C_RESET}"
            exit 1
        fi
    elif ! sudo -n true 2>/dev/null; then
        echo -e "${C_RED}[✗] Error: Root or passwordless sudo privileges are required to install into ${INSTALL_DIR} and ${BIN_DIR}.${C_RESET}"
        echo -e "${C_RED}    Please run with: curl -fsSL ... | sudo bash${C_RESET}"
        exit 1
    fi
    SUDO="sudo"
fi

echo -e "${C_BOLD}${C_CYAN}"
cat << 'EOF'
   ___                   _          _      ___            
  / _ \ _ __   ___ _ __ | |    __ _| |__  / _ \ _ __  ___ 
 | | | | '_ \ / _ \ '_ \| |   / _` | '_ \| | | | '_ \/ __|
 | |_| | |_) |  __/ | | | |__| (_| | |_) | |_| | |_) \__ \
  \___/| .__/ \___|_| |_|_____\__,_|_.__/ \___/| .__/|___/
       |_|                                     |_|        
EOF
echo -e "  Zero-Dependency Declarative Homelab Operations Engine${C_RESET}\n"

# 1. Preflight System Checks
echo -e "${C_BOLD}[1/4] Checking host environment...${C_RESET}"

# Python 3.10+ Check
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${C_RED}[✗] Error: Python 3 is not installed.${C_RESET}"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "${PY_VER}" | cut -d. -f1)
PY_MINOR=$(echo "${PY_VER}" | cut -d. -f2)

if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 10 ]; }; then
    echo -e "${C_RED}[✗] Error: OpenLabOps requires Python 3.10+, detected Python ${PY_VER}.${C_RESET}"
    exit 1
fi
echo -e "  ${C_GREEN}[✓]${C_RESET} Python ${PY_VER} detected (Standard Library only, 0 pip dependencies)"

# Git & SSH Checks
for tool in git ssh ssh-keygen; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo -e "${C_RED}[✗] Error: Required tool '${tool}' is not installed.${C_RESET}"
        exit 1
    fi
done
echo -e "  ${C_GREEN}[✓]${C_RESET} OpenSSH and Git toolchain detected"

# Ansible Advisory Check
if ! command -v ansible-playbook >/dev/null 2>&1; then
    echo -e "  ${C_YELLOW}[!] Notice: 'ansible-playbook' not found on PATH.${C_RESET}"
    echo -e "      OpenLabOps can run Day-0 setup, but Ansible is recommended for fleet orchestration."
fi

# 2. Synchronize / Clone Repository
echo -e "\n${C_BOLD}[2/4] Deploying OpenLabOps source to ${INSTALL_DIR}...${C_RESET}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo -e "  • Existing installation detected. Fetching latest main..."
    ${SUDO} git -C "${INSTALL_DIR}" pull --ff-only origin main || true
elif [ -d "${INSTALL_DIR}" ]; then
    echo -e "${C_RED}[✗] Error: ${INSTALL_DIR} exists but is not a git repository. Aborting to avoid overwriting unknown files.${C_RESET}"
    exit 1
else
    ${SUDO} mkdir -p "$(dirname "${INSTALL_DIR}")"
    ${SUDO} git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# Standardize permissions & AOT compile Python bytecode
${SUDO} chmod 0644 "${INSTALL_DIR}/VERSION" "${INSTALL_DIR}/tools/VERSION" 2>/dev/null || true
${SUDO} chmod -R 0755 "${INSTALL_DIR}/bin" "${INSTALL_DIR}/tools/bin" "${INSTALL_DIR}/tools/lib" "${INSTALL_DIR}/engine" 2>/dev/null || true
${SUDO} python3 -m compileall -f -q "${INSTALL_DIR}/tools/lib" "${INSTALL_DIR}/engine" 2>/dev/null || true
${SUDO} find "${INSTALL_DIR}/tools/lib" "${INSTALL_DIR}/engine" -name "*.pyc" -exec chmod 0644 {} + 2>/dev/null || true

# Ensure OpenSSH ControlMaster socket directory exists
mkdir -p "${HOME}/.ssh/sockets"
chmod 0700 "${HOME}/.ssh/sockets"

echo -e "  ${C_GREEN}[✓]${C_RESET} System installation directory ready at ${INSTALL_DIR}"

# 3. Setup CLI Binaries & Symlinks
echo -e "\n${C_BOLD}[3/4] Installing command symlinks into ${BIN_DIR}...${C_RESET}"
${SUDO} mkdir -p "${BIN_DIR}"

for cmd_path in "${INSTALL_DIR}"/tools/bin/* "${INSTALL_DIR}"/bin/lab-*; do
    if [ -f "${cmd_path}" ] && [ -x "${cmd_path}" ]; then
        cmd_name="$(basename "${cmd_path}")"
        ${SUDO} ln -sf "${cmd_path}" "${BIN_DIR}/${cmd_name}"
    fi
done

echo -e "  ${C_GREEN}[✓]${C_RESET} Commands symlinked to ${BIN_DIR}: lab-init, lab-node, lab-tools, lab-status, lab-backup, lab-ssh, lab-setup, lab-upgrade, lab-info, lab-config, lab-man, lab-test"

# 4. PATH Verification
echo -e "\n${C_BOLD}[4/4] Verifying PATH integration...${C_RESET}"
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    echo -e "  ${C_YELLOW}[!] Notice: ${BIN_DIR} is not in your current PATH.${C_RESET}"
    echo -e "      Add it to your shell configuration:"
    echo -e "      ${C_CYAN}export PATH=\"${BIN_DIR}:\${PATH}\"${C_RESET}"
else
    echo -e "  ${C_GREEN}[✓]${C_RESET} ${BIN_DIR} is already in PATH"
fi

echo -e "\n${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}  🎉 OpenLabOps has been installed successfully!${C_RESET}"
echo -e "${C_BOLD}${C_GREEN}======================================================================${C_RESET}"
echo -e "  Get started with your cluster onboarding:\n"
echo -e "    ${C_CYAN}lab-init${C_RESET}        Launch interactive Day-0 setup wizard"
echo -e "    ${C_CYAN}lab-tools${C_RESET}       Launch cluster management TUI"
echo -e "    ${C_CYAN}lab-node add${C_RESET}    Onboard a new node"
echo -e "    ${C_CYAN}lab-status${C_RESET}      Inspect fleet status and SSH key health\n"
