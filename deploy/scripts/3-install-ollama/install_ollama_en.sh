#!/bin/bash

MAGENTA='\e[35m'
CYAN='\e[36m'
BLUE='\e[34m'
GREEN='\e[32m'
YELLOW='\e[33m'
RED='\e[31m'
RESET='\e[0m'

# Initialize global variables
OS_ID=""
ARCH=""
OLLAMA_BIN_PATH="/usr/bin/ollama"
OLLAMA_LIB_DIR="/usr/lib/ollama"
OLLAMA_DATA_DIR="/var/lib/ollama"
SERVICE_FILE="/etc/systemd/system/ollama.service"
LOCAL_DIR="/home/eulercopilot/tools"
LOCAL_TGZ="ollama-linux-${ARCH}.tgz"

# Output function with timestamp
log() {
  local level=$1
  shift
  local color
  case "$level" in
    "INFO") color=${BLUE} ;;
    "SUCCESS") color=${GREEN} ;;
    "WARNING") color=${YELLOW} ;;
    "ERROR") color=${RED} ;;
    *) color=${RESET} ;;
  esac
  echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] $level: $*${RESET}"
}

# Network connection check
check_network() {
  local install_url=$(get_ollama_url)
  local domain=$(echo "$install_url" | awk -F/ '{print $3}')
  local test_url="http://$domain"

  log "INFO" "Checking network connection ($domain)..."
  if curl --silent --head --fail --connect-timeout 5 --max-time 10 "$test_url" >/dev/null 2>&1; then
    log "INFO" "Network connection normal"
    return 0
  else
    log "WARNING" "Unable to connect to internet"
    return 1
  fi
}

# Operating system detection
detect_os() {
  log "INFO" "Step 1/8: Detecting operating system and architecture..."
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID}"
    log "INFO" "Detected operating system: ${PRETTY_NAME}"
  else
    log "ERROR" "Unable to detect operating system type"
    exit 1
  fi

  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    armv7l)  ARCH="armv7" ;;
    *)       log "ERROR" "Unsupported architecture: $ARCH"; exit 1 ;;
  esac
  LOCAL_TGZ="ollama-linux-${ARCH}.tgz"
  log "INFO" "System architecture: $ARCH"
}

# Install system dependencies
install_dependencies() {
  log "INFO" "Step 2/8: Installing system dependencies..."
  local deps=(curl wget tar gzip jq)

  case "$OS_ID" in
    ubuntu|debian)
      if ! apt-get update; then
        log "ERROR" "APT source update failed"
        exit 1
      fi
      if ! DEBIAN_FRONTEND=noninteractive apt-get install -y "${deps[@]}"; then
        log "ERROR" "APT dependency installation failed"
        exit 1
      fi
      ;;
    centos|rhel|fedora|openEuler|kylin|uos)
      if ! yum install -y "${deps[@]}"; then
        log "ERROR" "YUM dependency installation failed"
        exit 1
      fi
      ;;
    *)
      log "ERROR" "Unsupported distribution: $OS_ID"
      exit 1
      ;;
  esac
  log "SUCCESS" "System dependencies installation completed"
}

# Get Ollama download URL
get_ollama_url() {
  echo "https://repo.oepkgs.net/openEuler/rpm/openEuler-22.03-LTS/contrib/eulercopilot/tools/$ARCH/ollama-linux-$ARCH.tgz"
}

install_ollama() {
  log "INFO" "Step 3/8: Installing Ollama core..."
  local install_url=$(get_ollama_url)
  local tmp_file="/tmp/ollama-${ARCH}.tgz"
  # Enhanced cleanup logic
  if [ -x "$OLLAMA_BIN_PATH" ] || [ -x "/usr/local/bin/ollama" ]; then
    log "WARNING" "Found existing Ollama installation, version: $($OLLAMA_BIN_PATH --version)"
    read -p "Reinstall? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "WARNING" "Found existing Ollama installation, cleaning up..."
        systemctl stop ollama 2>/dev/null || true
        systemctl disable ollama 2>/dev/null || true
        rm -rf ${SERVICE_FILE} 2>/dev/null
        rm $(which ollama) 2>/dev/null
        rm -rf ${OLLAMA_LIB_DIR} 2>/dev/null
        rm -rf ${OLLAMA_DATA_DIR} 2>/dev/null
        rm -rf /run/ollama 2>/dev/null
        userdel ollama 2>/dev/null || true
        groupdel ollama 2>/dev/null || true
    else
        return 0
    fi
  fi
    # Enhanced installation package handling
  local actual_tgz_path=""
  if [ -f "${LOCAL_DIR}/${LOCAL_TGZ}" ]; then
    log "INFO" "Using local installation package: ${LOCAL_DIR}/${LOCAL_TGZ}"
    actual_tgz_path="${LOCAL_DIR}/${LOCAL_TGZ}"
  else
    if ! check_network; then
      log "ERROR" "Network unavailable and no local installation package found"
      log "INFO" "Please pre-download ${LOCAL_TGZ} and place in ${LOCAL_DIR}"
      exit 1
    fi
    log "INFO" "Downloading installation package: ${install_url}"
    if ! wget --show-progress -q -O "${tmp_file}" "${install_url}"; then
      log "ERROR" "Download failed, exit code: $?"
      exit 1
    fi
    actual_tgz_path="${tmp_file}"
  fi

  log "INFO" "Extracting files to system directory /usr..."
  if ! tar -xzvf "$actual_tgz_path" -C /usr/; then
    log "ERROR" "Extraction failed, possible reasons:\n1. File corrupted\n2. Insufficient disk space\n3. Permission issues"
    exit 1
  fi

  chmod +x "$OLLAMA_BIN_PATH"
  if [ ! -x "$OLLAMA_BIN_PATH" ]; then
    log "ERROR" "Post-installation verification failed: executable file does not exist"
    exit 1
  fi
  log "SUCCESS" "Ollama core installation completed, version: $($OLLAMA_BIN_PATH --version || echo 'unknown')"
    # New: Create compatibility symbolic link
  if [ ! -L "/usr/local/bin/ollama" ]; then
    ln -sf "$OLLAMA_BIN_PATH" "/usr/local/bin/ollama"
    log "INFO" "Created symbolic link: /usr/local/bin/ollama → $OLLAMA_BIN_PATH"
  fi

  # Set library path
  echo "${OLLAMA_LIB_DIR}" > /etc/ld.so.conf.d/ollama.conf
  ldconfig
}

fix_user() {
  log "INFO" "Step 4/8: Fixing user configuration..."

  # Terminate all processes using ollama user
  if pgrep -u ollama >/dev/null; then
    log "WARNING" "Found running ollama processes, terminating..."
    pkill -9 -u ollama || true
    sleep 2
    if pgrep -u ollama >/dev/null; then
      log "ERROR" "Unable to terminate ollama user processes"
      exit 1
    fi
  fi

  # Clean up old user
  if id ollama &>/dev/null; then
    # Check if user is locked
    if passwd -S ollama | grep -q 'L'; then
      log "INFO" "Found locked ollama user, unlocking and setting random password..."
      random_pass=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 16)
      usermod -p "$(openssl passwd -1 "$random_pass")" ollama
    fi

    # Delete user and home directory
    if ! userdel -r ollama; then
      log "WARNING" "Unable to delete ollama user, attempting force delete..."
      if ! userdel -f -r ollama; then
        log "ERROR" "Force delete user failed, attempting manual cleanup..."
        sed -i '/^ollama:/d' /etc/passwd /etc/shadow /etc/group
        rm -rf /var/lib/ollama
        log "WARNING" "Manually cleaned up ollama user information"
      fi
    fi
    log "INFO" "Deleted old ollama user"
  fi

  # Check if group exists
  if getent group ollama >/dev/null; then
    log "INFO" "ollama group already exists, will use existing group"
    existing_group=true
  else
    existing_group=false
  fi

  # Create system user
  if ! useradd -r -g ollama -d /var/lib/ollama -s /bin/false ollama; then
    log "ERROR" "User creation failed, attempting manual creation..."

    # Create group if it doesn't exist
    if ! $existing_group; then
      if ! groupadd -r ollama; then
        log "ERROR" "Unable to create ollama group"
        exit 1
      fi
    fi

    # Try creating user again
    if ! useradd -r -g ollama -d /var/lib/ollama -s /bin/false ollama; then
      log "ERROR" "Manual user creation failed, please check:"
      log "ERROR" "1. Whether /etc/passwd and /etc/group files are writable"
      log "ERROR" "2. Whether there are conflicting users/groups in the system"
      log "ERROR" "3. System user limits (/etc/login.defs)"
      exit 1
    fi
  fi

  # Create directory structure
  mkdir -p /var/lib/ollama/.ollama/{models,bin}
  chown -R ollama:ollama /var/lib/ollama
  chmod -R 755 /var/lib/ollama
  log "SUCCESS" "User configuration fix completed"
}

fix_service() {
  log "INFO" "Step 5/8: Configuring system service..."
  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
Environment="OLLAMA_MODELS=${OLLAMA_DATA_DIR}/.ollama/models"
Environment="OLLAMA_HOST=0.0.0.0:11434"
ExecStart=${OLLAMA_BIN_PATH} serve
User=ollama
Group=ollama
Restart=failure
RestartSec=5
WorkingDirectory=/var/lib/ollama
RuntimeDirectory=ollama
RuntimeDirectoryMode=0755
StateDirectory=ollama
StateDirectoryMode=0755
CacheDirectory=ollama
CacheDirectoryMode=0755
LogsDirectory=ollama
LogsDirectoryMode=0755

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  log "SUCCESS" "Service configuration update completed"
}

# Restart service
restart_service() {
  log "INFO" "Step 6/8: Restarting service..."

  # Ensure service is stopped
  systemctl stop ollama || true

  # Ensure runtime directory exists
  mkdir -p /run/ollama
  chown ollama:ollama /run/ollama
  chmod 755 /run/ollama

  # Start service
  systemctl start ollama
  systemctl enable ollama

  log "SUCCESS" "Service restart completed"
}

# Final verification
final_check() {
  log "INFO" "Step 7/8: Performing final verification..."
  if ! command -v ollama &>/dev/null; then
    log "ERROR" "Ollama not properly installed"
    exit 1
  fi
  if ! ollama list &>/dev/null; then
    log "ERROR" "Service connection failed, please check:\n1.Service status: systemctl status ollama\n2.Port listening: ss -tuln | grep 11434"
    exit 1
  fi

  log "SUCCESS" "Verification passed, you can perform the following operations:\n  ollama list          # View model list\n  ollama run llama2    # Run example model"
}

### Main execution flow ###
main() {
  if [[ $EUID -ne 0 ]]; then
    log "ERROR" "Please run this script with sudo"
    exit 1
  fi

  detect_os
  install_dependencies
  echo -e "${MAGENTA}=== Starting Ollama Installation ===${RESET}"
  install_ollama
  fix_user
  fix_service
  restart_service
  if final_check; then
      echo -e "${MAGENTA}=== Ollama Installation Successful ===${RESET}"
  else
      echo -e "${MAGENTA}=== Ollama Installation Failed ===${RESET}"
  fi
}

main
