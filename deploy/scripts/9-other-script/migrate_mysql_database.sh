#!/bin/bash

# MySQL Database Recovery Script
# Description: Used for Euler Copilot project MySQL database recovery

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
print_color() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

log() {
    print_color "${GREEN}" "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

info() {
    print_color "${BLUE}" "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

warning() {
    print_color "${YELLOW}" "[$(date '+%Y-%m-%d %H:%M:%S')] Warning: $1"
}

error() {
    print_color "${RED}" "[$(date '+%Y-%m-%d %H:%M:%S')] Error: $1" >&2
    exit 1
}

step() {
    echo
    print_color "${PURPLE}" "[$(date '+%Y-%m-%d %H:%M:%S')] === $1 ==="
}

# Configuration variables
NAMESPACE="euler-copilot"
SECRET_NAME="authhub-secret"
PASSWORD_KEY="mysql-password"
DB_USER="authhub"
DB_NAME="oauth2"
BACKUP_FILE="/home/dump/mysql/mysql.sql"
POD_BACKUP_PATH="/home/mysql.sql"

# Show banner
show_banner() {
    echo
    print_color "${PURPLE}" "================================================"
    print_color "${PURPLE}" "            MySQL Database Recovery Script"
    print_color "${PURPLE}" "            Euler Copilot Project Specific"
    print_color "${PURPLE}" "================================================"
    echo
}

# Check required tools
check_dependencies() {
    step "Checking required tools"
    command -v kubectl >/dev/null 2>&1 || error "kubectl not installed"
    command -v base64 >/dev/null 2>&1 || error "base64 not installed"
    log "Dependency check passed"
}

# Get MySQL Pod name
get_mysql_pod() {
    step "Finding MySQL Pod"
    POD_NAME=$(kubectl get pod -n $NAMESPACE 2>/dev/null | grep mysql | grep Running | awk '{print $1}')

    if [ -z "$POD_NAME" ]; then
        error "No running MySQL Pod found"
    fi
    log "Found Pod: $POD_NAME"
}

# Get MySQL password
get_mysql_password() {
    step "Getting MySQL password"
    MYSQL_PASSWORD=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath="{.data.$PASSWORD_KEY}" 2>/dev/null | base64 --decode)

    if [ -z "$MYSQL_PASSWORD" ]; then
        error "Unable to get MySQL password, please check if secret exists"
    fi
    log "Password obtained successfully"
}

# Check if backup file exists
check_backup_file() {
    step "Checking backup file"
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file $BACKUP_FILE does not exist"
    fi

    # Display file information
    local file_size=$(du -h "$BACKUP_FILE" | cut -f1)
    local file_lines=$(wc -l < "$BACKUP_FILE" 2>/dev/null || echo "Unknown")
    info "File path: $BACKUP_FILE"
    info "File size: $file_size"
    info "File lines: $file_lines"

    log "Backup file check passed"
}

# Copy backup file to Pod
copy_backup_to_pod() {
    step "Copying backup file to Pod"
    info "Copying from local to Pod: $BACKUP_FILE -> $POD_NAME:$POD_BACKUP_PATH"

    kubectl cp "$BACKUP_FILE" "$POD_NAME:$POD_BACKUP_PATH" -n $NAMESPACE

    if [ $? -eq 0 ]; then
        log "Backup file copy completed"
    else
        error "File copy failed"
    fi
}

# Verify database connection
test_database_connection() {
    step "Testing database connection"
    info "Testing user $DB_USER connection to database $DB_NAME"

    kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' -e 'SELECT 1;' $DB_NAME 2>/dev/null
    " >/dev/null 2>&1

    if [ $? -eq 0 ]; then
        log "Database connection test successful"
    else
        error "Database connection failed, please check password and network connection"
    fi
}

# Execute database recovery
restore_database() {
    step "Executing database recovery"
    warning "This operation will overwrite existing database data!"

    info "Starting database recovery..."
    kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' $DB_NAME < $POD_BACKUP_PATH
    "

    local restore_status=$?

    if [ $restore_status -eq 0 ]; then
        log "Database recovery successful"
    else
        error "Database recovery failed, exit code: $restore_status"
    fi
}

# Verify recovery result
verify_restore() {
    step "Verifying recovery result"
    info "Checking database table information..."

    local table_count=$(kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
        mysql -u$DB_USER -p'$MYSQL_PASSWORD' -N -e \\
        \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$DB_NAME';\" 2>/dev/null
    " 2>/dev/null)

    if [ -n "$table_count" ] && [ "$table_count" -gt 0 ]; then
        log "Recovery verification successful, database contains $table_count tables"

        # Display some table names
        info "Database table list:"
        kubectl exec $POD_NAME -n $NAMESPACE -- bash -c "
            mysql -u$DB_USER -p'$MYSQL_PASSWORD' -e \\
            \"SELECT table_name FROM information_schema.tables WHERE table_schema = '$DB_NAME' LIMIT 10;\" 2>/dev/null
        " 2>/dev/null
    else
        warning "Unable to get table information, but recovery operation completed"
    fi
}

# Clean up temporary files
cleanup() {
    step "Cleaning up temporary files"
    info "Deleting backup file in Pod: $POD_BACKUP_PATH"

    kubectl exec $POD_NAME -n $NAMESPACE -- rm -f "$POD_BACKUP_PATH" 2>/dev/null || true

    log "Cleanup completed"
}

# Show usage instructions
usage() {
    show_banner
    print_color "${YELLOW}" "Usage: $0"
    echo
    print_color "${CYAN}" "Description: This script is used to recover MySQL database for Euler Copilot project"
    echo
    print_color "${CYAN}" "Prerequisites:"
    print_color "${WHITE}" "  1. kubectl configured and able to access cluster"
    print_color "${WHITE}" "  2. mysql.sql file exists in current directory"
    print_color "${WHITE}" "  3. Has sufficient cluster permissions"
    echo
    print_color "${RED}" "Warning: This operation will overwrite existing database data!"
    echo
}

# Confirm operation
confirm_operation() {
    print_color "${YELLOW}" "Warning: This operation will clear existing database data and import new data!"
    echo
    read -p "$(print_color "${YELLOW}" "Confirm execution of database recovery operation? (y/N): ")" confirm
    case $confirm in
        [yY] | [yY][eE][sS])
            return 0
            ;;
        *)
            warning "Operation cancelled"
            exit 0
            ;;
    esac
}

# Main function
main() {
    show_banner
    step "Starting MySQL database recovery process"

    check_dependencies
    get_mysql_pod
    get_mysql_password
    check_backup_file
    test_database_connection
    confirm_operation
    copy_backup_to_pod
    restore_database
    verify_restore
    cleanup

    echo
    print_color "${GREEN}" "================================================"
    print_color "${GREEN}" "           MySQL Data Recovery Completed!"
    print_color "${GREEN}" "================================================"
    echo
    print_color "${GREEN}" "✓ Backup file check completed"
    print_color "${GREEN}" "✓ Database connection test passed"
    print_color "${GREEN}" "✓ Data recovery executed successfully"
    print_color "${GREEN}" "✓ Temporary files cleanup completed"
    echo
    print_color "${BLUE}" "Tip: It is recommended to check application running status to ensure data recovery success."
}

# Script entry point
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

main
