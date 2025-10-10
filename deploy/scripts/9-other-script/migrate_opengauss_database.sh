#!/bin/bash

# OpenGauss Database Import Script
# Description: Used for Euler Copilot project database data import

set -e  # Exit immediately on error

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] Warning: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] Error: $1${NC}" >&2
    exit 1
}

step() {
    echo -e "${PURPLE}[$(date '+%Y-%m-%d %H:%M:%S')] === $1 ===${NC}"
}

# Configuration variables
NAMESPACE="euler-copilot"
SECRET_NAME="euler-copilot-database"
PASSWORD_KEY="gauss-password"
BACKUP_FILE="/home/dump/opengauss/opengauss.sql"
POD_BACKUP_PATH="/home/omm/opengauss.sql"

# Check required tools
check_dependencies() {
    step "Checking required tools"
    command -v kubectl >/dev/null 2>&1 || error "kubectl not installed"
    command -v base64 >/dev/null 2>&1 || error "base64 not installed"
    log "Dependency check passed"
}

# Get database password
get_database_password() {
    step "Getting database password"
    PASSWORD=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath="{.data.$PASSWORD_KEY}" 2>/dev/null | base64 --decode)

    if [ -z "$PASSWORD" ]; then
        error "Unable to get database password, please check if secret exists"
    fi
    log "Password obtained successfully"
}

# Get OpenGauss Pod name
get_opengauss_pod() {
    step "Finding OpenGauss Pod"
    POD_NAME=$(kubectl get pod -n $NAMESPACE 2>/dev/null | grep opengauss | grep Running | awk '{print $1}')

    if [ -z "$POD_NAME" ]; then
        error "No running OpenGauss Pod found"
    fi
    log "Found Pod: $POD_NAME"
}

# Check if backup file exists
check_backup_file() {
    step "Checking backup file"
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file $BACKUP_FILE does not exist"
    fi
    log "Backup file check passed: $BACKUP_FILE"
}

# Copy backup file to Pod
copy_backup_to_pod() {
    step "Copying backup file to Pod"
    kubectl cp "$BACKUP_FILE" "$POD_NAME:$POD_BACKUP_PATH" -n $NAMESPACE
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- bash -c "chown omm:omm $POD_BACKUP_PATH"
    log "Backup file copy completed"
}

# Execute database import
import_database() {
    step "Executing database import operation"

    info "Step 1: Disabling foreign key constraints..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = replica;\""
    log "Foreign key constraints disabled"

    info "Step 2: Clearing table data..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"
TRUNCATE TABLE
    action, team, knowledge_base, document, chunk, document_type,
    role, role_action, users, task, task_report, team_user, user_role,
    dataset, dataset_doc, image, qa, task_queue, team_message,
    testcase, testing, user_message
CASCADE;\""
    log "Table data cleared"

    info "Step 3: Importing data..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -f $POD_BACKUP_PATH -W '$PASSWORD'"
    log "Data import completed"

    info "Step 4: Enabling foreign key constraints..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = origin;\""
    log "Foreign key constraints enabled"

    log "Database import operation fully completed"
}

# Clean up temporary files
cleanup() {
    step "Cleaning up temporary files"
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- rm -f "$POD_BACKUP_PATH" 2>/dev/null || true
    log "Cleanup completed"
}

# Show banner
show_banner() {
    echo -e "${PURPLE}"
    echo "================================================================"
    echo "                OpenGauss Database Import Script"
    echo "                Euler Copilot Project Specific"
    echo "================================================================"
    echo -e "${NC}"
}

# Main function
main() {
    show_banner
    step "Starting OpenGauss database import process"

    check_dependencies
    get_database_password
    get_opengauss_pod
    check_backup_file
    copy_backup_to_pod
    import_database
    cleanup

    echo -e "${GREEN}"
    echo "================================================================"
    echo "                   OpenGauss Data Import Completed!"
    echo "================================================================"
    echo -e "${NC}"

    echo -e "${GREEN}✓ Foreign key constraints disabled${NC}"
    echo -e "${GREEN}✓ Table data cleared${NC}"
    echo -e "${GREEN}✓ New data imported${NC}"
    echo -e "${GREEN}✓ Foreign key constraints re-enabled${NC}"
    echo ""
    echo -e "${BLUE}Tip: It is recommended to check application running status to ensure data import success.${NC}"
}

# Show usage instructions
usage() {
    show_banner
    echo -e "${YELLOW}Usage: $0${NC}"
    echo ""
    echo -e "Description: This script is used to import OpenGauss database data for Euler Copilot project"
    echo ""
    echo -e "${CYAN}Prerequisites:${NC}"
    echo -e "  1. kubectl configured and able to access cluster"
    echo -e "  2. opengauss.sql file exists in current directory"
    echo -e "  3. Has sufficient cluster permissions"
    echo ""
    echo -e "${RED}Warning: This operation will clear existing database data and import new data!${NC}"
}

# Script entry point
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

# Fix color display issue
echo -e "${YELLOW}Warning: This operation will clear existing database data and import new data!${NC}"

# Method 1: Use temporary variable
yellow_text="${YELLOW}Confirm execution of database import operation? (y/N): ${NC}"
read -p "$(echo -e "$yellow_text")" confirm

# Method 2: Or use echo -e directly (alternative)
# echo -e "${YELLOW}Confirm execution of database import operation? (y/N): ${NC}\c"
# read confirm

case $confirm in
    [yY] | [yY][eE][sS])
        main
        ;;
    *)
        warning "Operation cancelled"
        exit 0
        ;;
esac
