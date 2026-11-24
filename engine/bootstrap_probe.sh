#!/bin/sh
# ==============================================================================
# OpenLabOps - Node Bootstrap & Sensory Probe Script
# Pure POSIX Shell - Compatible with Linux (Photon, Arch, Debian, RHEL, Alpine) & Linux
#
# Usage:
#   BOOTSTRAP_USER=lab \
#   BOOTSTRAP_PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5..." \
#   BOOTSTRAP_KEY_OPTIONS='from="192.168.1.0/24"' \
#   sh bootstrap_probe.sh
# ==============================================================================
set -eu

BOOTSTRAP_USER="${BOOTSTRAP_USER:-lab}"
BOOTSTRAP_PUBKEY="${BOOTSTRAP_PUBKEY:-}"
BOOTSTRAP_KEY_OPTIONS="${BOOTSTRAP_KEY_OPTIONS:-}"
SKIP_DOOR="${SKIP_DOOR:-false}"

SYSTEM_UNAME=$(uname -s)

# ==============================================================================
# 1. 開第一道門：針對常規系統、韌體嵌入式或 Hypervisor 專屬開門
# ==============================================================================
NODE_CATEGORY="server"
IS_IMMUTABLE="false"
APPLIANCE_TYPE="none"
KEY_PROFILE="standard"

# 1.0 先行探測是否為特殊韌體設備或 Hypervisor
if command -v pveversion >/dev/null 2>&1 || [ -d /etc/pve ]; then
    NODE_CATEGORY="hypervisor"
    IS_IMMUTABLE="false"
    APPLIANCE_TYPE="pve"
    KEY_PROFILE="standard"
    OS_FAMILY="Debian"
    DISTRO_NAME="Proxmox VE"
    DISTRO_VERSION=$(pveversion 2>/dev/null | cut -d/ -f2 || echo "PVE")
elif [ -f /etc/pfSense-ddb ] || [ -f /etc/inc/pfsense-utils.inc ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="pfsense"
    KEY_PROFILE="standard"
    OS_FAMILY="Linux"
    DISTRO_NAME="pfSense"
elif [ -d /usr/local/opnsense ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="opnsense"
    KEY_PROFILE="standard"
    OS_FAMILY="Linux"
    DISTRO_NAME="OPNsense"
elif [ -f /etc/truenas-build-version ] || ( [ -f /etc/version ] && grep -iq "truenas" /etc/version 2>/dev/null ) || command -v midclt >/dev/null 2>&1; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="truenas"
    KEY_PROFILE="standard"
    OS_FAMILY="Debian"
    DISTRO_NAME="TrueNAS"
    DISTRO_VERSION=$(cat /etc/version 2>/dev/null || echo "SCALE")
elif [ -f /etc/synoinfo.conf ] || [ -f /etc.defaults/VERSION ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="synology"
    KEY_PROFILE="standard"
    OS_FAMILY="Linux"
    DISTRO_NAME="Synology DSM"
    DISTRO_VERSION="7.2"
elif [ -f /etc/config/uLinux.conf ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="qnap"
    KEY_PROFILE="standard"
    OS_FAMILY="Linux"
    DISTRO_NAME="QNAP QTS"
    DISTRO_VERSION="5.1"
elif [ -f /etc/unraid-version ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="true"
    APPLIANCE_TYPE="unraid"
    KEY_PROFILE="standard"
    OS_FAMILY="Linux"
    DISTRO_NAME="Unraid"
    DISTRO_VERSION=$(cat /etc/unraid-version 2>/dev/null || echo "6.12")
elif [ -f /etc/openmediavault/config.xml ]; then
    NODE_CATEGORY="appliance"
    IS_IMMUTABLE="false"
    APPLIANCE_TYPE="omv"
    KEY_PROFILE="standard"
    OS_FAMILY="Debian"
    DISTRO_NAME="OpenMediaVault"
    DISTRO_VERSION="7.0"
fi

if [ "$SKIP_DOOR" != "true" ] && [ -n "$BOOTSTRAP_PUBKEY" ]; then
    ENTRY=""
    if [ -n "$BOOTSTRAP_KEY_OPTIONS" ]; then
        ENTRY="$BOOTSTRAP_KEY_OPTIONS $BOOTSTRAP_PUBKEY"
    else
        ENTRY="$BOOTSTRAP_PUBKEY"
    fi

    # 常規分支: 標準 Linux 系統
    if true; then
        # 1.0.1 缺乏工具主動補齊 (主動安裝 sudo, python3, iproute2, procps 以統一程式碼與 IaC 基礎)
        if [ "$SYSTEM_UNAME" = "Linux" ]; then
            NEED_INSTALL=""
            ! command -v sudo >/dev/null 2>&1 && NEED_INSTALL="yes"
            ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1 && NEED_INSTALL="yes"
            ! command -v ip >/dev/null 2>&1 && NEED_INSTALL="yes"
            ! command -v ps >/dev/null 2>&1 && NEED_INSTALL="yes"

            if [ "$NEED_INSTALL" = "yes" ]; then
                if command -v pacman >/dev/null 2>&1; then
                    pacman -Sy --noconfirm --needed sudo python iproute2 procps-ng >/dev/null 2>&1 || true
                elif command -v apt-get >/dev/null 2>&1; then
                    DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
                    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sudo python3 iproute2 procps >/dev/null 2>&1 || true
                elif command -v microdnf >/dev/null 2>&1; then
                    microdnf install -y sudo python3 iproute procps-ng >/dev/null 2>&1 || true
                elif command -v dnf >/dev/null 2>&1; then
                    dnf install -y sudo python3 iproute procps-ng >/dev/null 2>&1 || true
                elif command -v tdnf >/dev/null 2>&1; then
                    tdnf install -y sudo python3 iproute2 procps-ng >/dev/null 2>&1 || true
                elif command -v apk >/dev/null 2>&1; then
                    apk add --no-cache sudo python3 bash iproute2 procps >/dev/null 2>&1 || true
                fi
            fi
        fi

        # 1.1 建立使用者
        if ! id "$BOOTSTRAP_USER" >/dev/null 2>&1; then
            if [ "$SYSTEM_UNAME" = "Linux" ]; then
                pw useradd "$BOOTSTRAP_USER" -m -s /bin/sh -G wheel
            elif command -v useradd >/dev/null 2>&1; then
                useradd -m -s /bin/bash "$BOOTSTRAP_USER" 2>/dev/null || useradd -m -s /bin/sh "$BOOTSTRAP_USER"
            elif command -v adduser >/dev/null 2>&1; then
                adduser -D -s /bin/sh "$BOOTSTRAP_USER" 2>/dev/null || adduser --disabled-password --gecos "" "$BOOTSTRAP_USER"
            fi
        fi

        # 確保使用者帳號未被 shadow 鎖定 (Alpine ! 或 RHEL/Oracle !! 預設鎖定導致拒絕公鑰認證)
        if [ -f /etc/shadow ]; then
            sed -i "s/^${BOOTSTRAP_USER}:!!*:/${BOOTSTRAP_USER}:*:/" /etc/shadow 2>/dev/null || true
        fi
        passwd -u "$BOOTSTRAP_USER" >/dev/null 2>&1 || true

        # 1.2 取得家目錄
        USER_HOME=""
        if command -v getent >/dev/null 2>&1; then
            USER_HOME=$(getent passwd "$BOOTSTRAP_USER" 2>/dev/null | cut -d: -f6 || true)
        fi
        if [ -z "$USER_HOME" ] && [ -f /etc/passwd ]; then
            USER_HOME=$(grep -E "^${BOOTSTRAP_USER}:" /etc/passwd 2>/dev/null | cut -d: -f6 || true)
        fi
        if [ -z "$USER_HOME" ] || [ ! -d "$USER_HOME" ]; then
            USER_HOME="/home/$BOOTSTRAP_USER"
            mkdir -p "$USER_HOME"
        fi

        # 1.3 配置群組與免密 Sudoers
        if [ "$SYSTEM_UNAME" = "Linux" ]; then
            pw groupmod wheel -m "$BOOTSTRAP_USER" >/dev/null 2>&1 || true
            SUDO_DIR="/usr/local/etc/sudoers.d"
        else
            if command -v usermod >/dev/null 2>&1; then
                if grep -q "^sudo:" /etc/group 2>/dev/null; then
                    usermod -aG sudo "$BOOTSTRAP_USER" >/dev/null 2>&1 || true
                elif grep -q "^wheel:" /etc/group 2>/dev/null; then
                    usermod -aG wheel "$BOOTSTRAP_USER" >/dev/null 2>&1 || true
                fi
            fi
            SUDO_DIR="/etc/sudoers.d"
        fi

        if [ -d "$SUDO_DIR" ] || mkdir -p "$SUDO_DIR" 2>/dev/null; then
            SUDO_FILE="$SUDO_DIR/zz-$BOOTSTRAP_USER"
            rm -f "$SUDO_DIR/$BOOTSTRAP_USER" "$SUDO_DIR/99-$BOOTSTRAP_USER" 2>/dev/null || true
            echo "$BOOTSTRAP_USER ALL=(ALL:ALL) NOPASSWD: ALL" > "$SUDO_FILE"
            chmod 0440 "$SUDO_FILE"
            if command -v visudo >/dev/null 2>&1; then
                if ! visudo -cf "$SUDO_FILE" >/dev/null 2>&1; then
                    rm -f "$SUDO_FILE"
                fi
            fi
        fi

        # 1.4 寫入 Authorized Keys
        SSH_DIR="$USER_HOME/.ssh"
        AUTH_FILE="$SSH_DIR/authorized_keys"
        mkdir -p "$SSH_DIR"
        chmod 0700 "$SSH_DIR"

        if [ -f "$AUTH_FILE" ]; then
            if ! grep -F "$BOOTSTRAP_PUBKEY" "$AUTH_FILE" >/dev/null 2>&1; then
                echo "$ENTRY" >> "$AUTH_FILE"
            fi
        else
            echo "$ENTRY" > "$AUTH_FILE"
        fi

        chmod 0600 "$AUTH_FILE"
        if [ "$SYSTEM_UNAME" = "Linux" ]; then
            chown -R "$BOOTSTRAP_USER:wheel" "$SSH_DIR" 2>/dev/null || chown -R "$BOOTSTRAP_USER" "$SSH_DIR"
        else
            chown -R "$BOOTSTRAP_USER:$BOOTSTRAP_USER" "$SSH_DIR" 2>/dev/null || chown -R "$BOOTSTRAP_USER" "$SSH_DIR"
        fi
        if command -v restorecon >/dev/null 2>&1; then
            restorecon -RF "$SSH_DIR" >/dev/null 2>&1 || true
        fi

        # 1.5 確保 SSH 服務開機自啟
        if command -v systemctl >/dev/null 2>&1; then
            systemctl enable sshd >/dev/null 2>&1 || systemctl enable ssh >/dev/null 2>&1 || true
            systemctl start sshd >/dev/null 2>&1 || systemctl start ssh >/dev/null 2>&1 || true
        elif [ "$SYSTEM_UNAME" = "Linux" ]; then
            sysrc sshd_enable="YES" >/dev/null 2>&1 || true
            service sshd start >/dev/null 2>&1 || true
        elif command -v rc-service >/dev/null 2>&1; then
            rc-service sshd start >/dev/null 2>&1 || true
        elif command -v service >/dev/null 2>&1; then
            service sshd start >/dev/null 2>&1 || service ssh start >/dev/null 2>&1 || true
        fi
    fi
fi

# ==============================================================================
# 2. 現場事實採集 (Ground Truth Sensory Probing)
# ==============================================================================

# 2.1 主機名稱與 FQDN
HOSTNAME=$(hostname 2>/dev/null || uname -n)
FQDN=$(hostname -f 2>/dev/null || echo "$HOSTNAME")

# 2.2 作業系統分類與發行版 (若非韌體設備才進行常規檢測)
KERNEL=$(uname -r)
ARCH=$(uname -m)

if [ "$APPLIANCE_TYPE" = "none" ]; then
    OS_FAMILY="Unknown"
    DISTRO_NAME="Unknown"
    DISTRO_VERSION="Unknown"
    if [ "$SYSTEM_UNAME" = "Linux" ]; then
        OS_FAMILY="Linux"
        DISTRO_NAME="Linux"
        DISTRO_VERSION=$(linux-version 2>/dev/null || uname -r)
    elif [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_NAME="${NAME:-Linux}"
        DISTRO_VERSION="${VERSION_ID:-unknown}"
        if command -v tr >/dev/null 2>&1; then
            ID_LOWER=$(echo "${ID:-linux}" | tr '[:upper:]' '[:lower:]')
        else
            ID_LOWER="${ID:-linux}"
        fi

        case "$ID_LOWER" in
            photon|[pP][hH][oO][tT][oO][nN])
                OS_FAMILY="PhotonOS"
                ;;
            arch|endeavouros|manjaro|[aA][rR][cC][hH]*)
                OS_FAMILY="ArchLinux"
                ;;
            linux|[fF][rR][eE][eE][bB][sS][dD])
                OS_FAMILY="Linux"
                ;;
            ol|oracle|rhel|centos|rocky|almalinux|fedora|[oO][lL]|[rR][hH][eE][lL]*)
                OS_FAMILY="OracleLinux"
                ;;
            debian|ubuntu|pop|mint|[dD][eE][bB][iI][aA][nN]|[uU][bB][uU][nN][tT][uU])
                OS_FAMILY="Debian"
                ;;
            alpine|[aA][lL][pP][iI][nN][eE])
                OS_FAMILY="Alpine"
                ;;
            opensuse*|sles|[sS][uU][sS][eE]*)
                OS_FAMILY="Suse"
                ;;
            *)
                OS_FAMILY="Linux"
                ;;
        esac
    fi
fi

# 2.3 網路探測 (Primary IP, Gateway, MAC, Subnet)
PRIMARY_IP=""
DEFAULT_GW=""
PRIMARY_IFACE=""
MAC_ADDR=""
SUBNET_CIDR=""

if command -v ip >/dev/null 2>&1; then
    # Linux ip route
    DEFAULT_ROUTE=$(ip route show default 2>/dev/null | head -n 1 || true)
    if [ -n "$DEFAULT_ROUTE" ]; then
        set -- $DEFAULT_ROUTE
        while [ $# -gt 0 ]; do
            if [ "$1" = "via" ]; then
                DEFAULT_GW="$2"
            elif [ "$1" = "dev" ]; then
                PRIMARY_IFACE="$2"
            fi
            shift
        done
    fi

    # Fallback interface if default route didn't have dev
    if [ -z "$PRIMARY_IFACE" ]; then
        DEV_CANDIDATE=$(ip -o link show 2>/dev/null | grep -v 'lo:' | head -n 1 | cut -d: -f2 || true)
        if [ -n "$DEV_CANDIDATE" ]; then
            set -- $DEV_CANDIDATE
            PRIMARY_IFACE="$1"
        fi
    fi

    if [ -n "$PRIMARY_IFACE" ]; then
        IP_LINE=$(ip -4 addr show dev "$PRIMARY_IFACE" 2>/dev/null | grep -w inet | head -n 1 || true)
        if [ -n "$IP_LINE" ]; then
            set -- $IP_LINE
            IP_CIDR="$2"
            PRIMARY_IP=$(echo "$IP_CIDR" | cut -d/ -f1)
            PREFIX=$(echo "$IP_CIDR" | cut -d/ -f2)
            if [ "$PREFIX" = "24" ]; then
                NET_PREFIX=$(echo "$PRIMARY_IP" | cut -d. -f1-3)
                SUBNET_CIDR="${NET_PREFIX}.0/24"
            elif [ "$PREFIX" = "16" ]; then
                NET_PREFIX=$(echo "$PRIMARY_IP" | cut -d. -f1-2)
                SUBNET_CIDR="${NET_PREFIX}.0.0/16"
            elif [ "$PREFIX" = "25" ]; then
                OCTET4=$(echo "$PRIMARY_IP" | cut -d. -f4)
                NET_PREFIX=$(echo "$PRIMARY_IP" | cut -d. -f1-3)
                if [ "$OCTET4" -ge 128 ]; then
                    SUBNET_CIDR="${NET_PREFIX}.128/25"
                else
                    SUBNET_CIDR="${NET_PREFIX}.0/25"
                fi
            else
                SUBNET_CIDR="$IP_CIDR"
            fi
        fi

        MAC_LINE=$(ip link show dev "$PRIMARY_IFACE" 2>/dev/null | grep -w link/ether | head -n 1 || true)
        if [ -n "$MAC_LINE" ]; then
            set -- $MAC_LINE
            MAC_ADDR="$2"
        fi
    fi
elif [ "$SYSTEM_UNAME" = "Linux" ] || command -v netstat >/dev/null 2>&1; then
    # Linux netstat / route
    DEFAULT_LINE=$(netstat -rn 2>/dev/null | grep -E '^default' | head -n 1 || true)
    if [ -n "$DEFAULT_LINE" ]; then
        set -- $DEFAULT_LINE
        DEFAULT_GW="$2"
        PRIMARY_IFACE="$4"
    fi
    if [ -n "$PRIMARY_IFACE" ]; then
        IF_INET=$(ifconfig "$PRIMARY_IFACE" 2>/dev/null | grep -w inet | head -n 1 || true)
        if [ -n "$IF_INET" ]; then
            set -- $IF_INET
            PRIMARY_IP="$2"
            NET_PREFIX=$(echo "$PRIMARY_IP" | cut -d. -f1-3)
            SUBNET_CIDR="${NET_PREFIX}.0/24"
        fi
        IF_ETH=$(ifconfig "$PRIMARY_IFACE" 2>/dev/null | grep -w ether | head -n 1 || true)
        if [ -n "$IF_ETH" ]; then
            set -- $IF_ETH
            MAC_ADDR="$2"
        fi
    fi
fi

# Fallback IP detection
if [ -z "$PRIMARY_IP" ]; then
    H_IPS=$(hostname -I 2>/dev/null || true)
    if [ -n "$H_IPS" ]; then
        set -- $H_IPS
        PRIMARY_IP="$1"
    else
        PRIMARY_IP="127.0.0.1"
    fi
fi

# Fallback Default Gateway if empty
if [ -z "$DEFAULT_GW" ] && [ -n "$PRIMARY_IP" ] && [ "$PRIMARY_IP" != "127.0.0.1" ]; then
    NET_PREFIX=$(echo "$PRIMARY_IP" | cut -d. -f1-3)
    DEFAULT_GW="${NET_PREFIX}.1"
fi

# 2.4 能力探測 (Capabilities)
HAS_DOCKER="false"
DOCKER_VER=""
if command -v docker >/dev/null 2>&1; then
    HAS_DOCKER="true"
    D_OUT=$(docker --version 2>/dev/null || true)
    if [ -n "$D_OUT" ]; then
        set -- $D_OUT
        DOCKER_VER=$(echo "$3" | cut -d, -f1)
    fi
    [ -z "$DOCKER_VER" ] && DOCKER_VER="installed"
fi

HAS_CONTAINERD="false"
if command -v containerd >/dev/null 2>&1; then
    HAS_CONTAINERD="true"
fi

HAS_PYTHON="false"
PYTHON_VER=""
if command -v python3 >/dev/null 2>&1; then
    HAS_PYTHON="true"
    PY_OUT=$(python3 --version 2>&1 || true)
    if [ -n "$PY_OUT" ]; then
        set -- $PY_OUT
        PYTHON_VER="$2"
    fi
    [ -z "$PYTHON_VER" ] && PYTHON_VER="python3"
elif command -v python >/dev/null 2>&1; then
    HAS_PYTHON="true"
    PY_OUT=$(python --version 2>&1 || true)
    if [ -n "$PY_OUT" ]; then
        set -- $PY_OUT
        PYTHON_VER="$2"
    fi
    [ -z "$PYTHON_VER" ] && PYTHON_VER="python"
fi

# 2.5 硬體規格 (Hardware)
CPU_CORES=1
if command -v nproc >/dev/null 2>&1; then
    CPU_CORES=$(nproc 2>/dev/null || echo 1)
elif [ "$SYSTEM_UNAME" = "Linux" ]; then
    CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
elif [ -f /proc/cpuinfo ]; then
    CPU_CORES=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 1)
fi

MEMORY_MB=1024
if [ -f /proc/meminfo ]; then
    while read -r _line; do
        case "$_line" in
            MemTotal:*)
                set -- $_line
                MEM_KB="$2"
                MEMORY_MB=$((MEM_KB / 1024))
                break
                ;;
        esac
    done < /proc/meminfo
elif [ "$SYSTEM_UNAME" = "Linux" ]; then
    MEM_BYTES=$(sysctl -n hw.physmem 2>/dev/null || echo 1073741824)
    MEMORY_MB=$((MEM_BYTES / 1024 / 1024))
fi

DISK_TOTAL_GB=20
DF_OUT=$(df -k / 2>/dev/null | tail -n 1 || true)
if [ -n "$DF_OUT" ]; then
    set -- $DF_OUT
    DISK_KB="$2"
    DISK_TOTAL_GB=$((DISK_KB / 1024 / 1024))
fi

# ==============================================================================
# 3. 輸出結構化 JSON 事實 (Delimited for Caller)
# ==============================================================================
echo "===OPENLAB_NODE_JSON_START==="
cat <<EOF
{
  "hostname": "$HOSTNAME",
  "fqdn": "$FQDN",
  "node_category": "$NODE_CATEGORY",
  "is_immutable": $IS_IMMUTABLE,
  "appliance_type": "$APPLIANCE_TYPE",
  "key_profile": "$KEY_PROFILE",
  "os_family": "$OS_FAMILY",
  "distribution": "$DISTRO_NAME",
  "version": "$DISTRO_VERSION",
  "kernel": "$KERNEL",
  "architecture": "$ARCH",
  "primary_ip": "$PRIMARY_IP",
  "subnet_cidr": "$SUBNET_CIDR",
  "default_gateway": "$DEFAULT_GW",
  "mac_address": "$MAC_ADDR",
  "capabilities": {
    "has_docker": $HAS_DOCKER,
    "docker_version": "$DOCKER_VER",
    "has_containerd": $HAS_CONTAINERD,
    "has_python": $HAS_PYTHON,
    "python_version": "$PYTHON_VER"
  },
  "hardware": {
    "cpu_cores": $CPU_CORES,
    "memory_mb": $MEMORY_MB,
    "disk_total_gb": $DISK_TOTAL_GB
  },
  "bootstrap_door_ready": true
}
EOF
echo "===OPENLAB_NODE_JSON_END==="
