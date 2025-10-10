#!/bin/bash
set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Backup directories
BACKUP_BASE="/home/dump"
MYSQL_BACKUP_DIR="$BACKUP_BASE/mysql"
OPENGAUSS_BACKUP_DIR="$BACKUP_BASE/opengauss"
MINIO_BACKUP_DIR="$BACKUP_BASE/minio"
OPENGAUSS_DATA_PATH="/home/omm/opengauss.sql"
MYSQL_DATA_PATH="/home/mysql.sql"
MYSQL_USER="authhub"
MYSQL_DB_NAME="oauth2"
MYSQL_TABLE_NAME="user"
GS_USERNAME="postgres"
GS_DB="postgres"

# Timestamp function
timestamp() {
    echo -n "$(date '+%Y-%m-%d %H:%M:%S')"
}

# Log functions
log_info() {
    echo -e "$(timestamp) ${BLUE}=== $1 ${NC}"
}

log_success() {
    echo -e "$(timestamp) ${GREEN}$1${NC}"
}

log_warning() {
    echo -e "$(timestamp) ${YELLOW}$1${NC}"
}

log_error() {
    echo -e "$(timestamp) ${RED}$1${NC}"
}

log_step() {
    echo -e "$(timestamp) ${PURPLE} $1 ${NC}"
}

# Print banner
print_banner() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "                  Euler Copilot Data Backup Script"
    echo "                     MySQL + OpenGauss + MinIO"
    echo "================================================================"
    echo -e "${NC}"
}

print_completion_banner() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "             MySQL + OpenGauss + MinIO Data Backup Completed!"
    echo "================================================================"
    echo -e "${NC}"
}

# Check command execution result
check_command() {
    if [ $? -eq 0 ]; then
        log_success "$1"
    else
        log_error "$2"
        exit 1
    fi
}

# Create backup directories
create_backup_directories() {
    log_step "Creating backup directories"

    mkdir -p "$MYSQL_BACKUP_DIR" "$OPENGAUSS_BACKUP_DIR" "$MINIO_BACKUP_DIR"
    check_command "Backup directories created" "Failed to create backup directories"

    log_info "MySQL backup directory: $MYSQL_BACKUP_DIR"
    log_info "OpenGauss backup directory: $OPENGAUSS_BACKUP_DIR"
    log_info "MinIO backup directory: $MINIO_BACKUP_DIR"
}

# Backup MySQL data
backup_mysql() {
    log_step "Starting MySQL data backup"

    # Get MySQL Pod name
    log_info "Finding MySQL Pod..."
    local pod_name=$(kubectl get pod -n euler-copilot | grep mysql | awk '{print $1}')
    if [ -z "$pod_name" ]; then
        log_error "MySQL Pod not found"
        return 1
    fi
    log_success "Found Pod: $pod_name"

    # Get MySQL password
    log_info "Getting MySQL password..."
    local mysql_password=$(kubectl get secret authhub-secret -n euler-copilot -o jsonpath='{.data.mysql-password}' | base64 --decode)
    if [ -z "$mysql_password" ]; then
        log_error "Failed to get MySQL password"
        return 1
    fi
    log_success "Password obtained successfully"

    # Export user table
    log_info "Exporting user table data..."
    kubectl exec $pod_name -n euler-copilot -- bash -c "mysqldump -u${MYSQL_USER} -p${mysql_password} --no-tablespaces ${MYSQL_DB_NAME} ${MYSQL_TABLE_NAME} > ${MYSQL_DATA_PATH}"
    check_command "User table export completed" "User table export failed"

    # Copy backup file to local
    log_info "Copying backup file to local..."
    kubectl cp $pod_name:${MYSQL_DATA_PATH} $MYSQL_BACKUP_DIR/mysql.sql -n euler-copilot
    check_command "MySQL backup file copy completed" "MySQL backup file copy failed"

    # Verify backup file
    if [ -f "$MYSQL_BACKUP_DIR/mysql.sql" ]; then
        local file_size=$(du -h "$MYSQL_BACKUP_DIR/mysql.sql" | cut -f1)
        log_success "MySQL backup completed, file size: $file_size"
    else
        log_error "MySQL backup file not found"
        return 1
    fi
}

# Backup OpenGauss data
backup_opengauss() {
    log_step "Starting OpenGauss data backup"

    # Get OpenGauss Pod name
    log_info "Finding OpenGauss Pod..."
    local pod_name=$(kubectl get pod -n euler-copilot | grep opengauss | awk '{print $1}')
    if [ -z "$pod_name" ]; then
        log_error "OpenGauss Pod not found"
        return 1
    fi
    log_success "Found Pod: $pod_name"

    # Get OpenGauss password
    log_info "Getting OpenGauss password..."
    local gauss_password=$(kubectl get secret euler-copilot-database -n euler-copilot -o jsonpath='{.data.gauss-password}' | base64 --decode)
    if [ -z "$gauss_password" ]; then
        log_error "Failed to get OpenGauss password"
        return 1
    fi
    log_success "Password obtained successfully"

    # Export database
    log_info "Exporting OpenGauss database..."
    kubectl exec -it "$pod_name" -n euler-copilot -- /bin/sh -c "su - omm -c 'source ~/.bashrc && gs_dump -U ${GS_USERNAME} -f ${OPENGAUSS_DATA_PATH} -p 5432 ${GS_DB} -F p -W \"${gauss_password}\"'"
    check_command "OpenGauss database export completed" "OpenGauss database export failed"

    # Copy backup file to local
    log_info "Copying backup file to local..."
    kubectl cp $pod_name:${OPENGAUSS_DATA_PATH} $OPENGAUSS_BACKUP_DIR/opengauss.sql -n euler-copilot
    check_command "OpenGauss backup file copy completed" "OpenGauss backup file copy failed"

    # Verify backup file
    if [ -f "$OPENGAUSS_BACKUP_DIR/opengauss.sql" ]; then
        local file_size=$(du -h "$OPENGAUSS_BACKUP_DIR/opengauss.sql" | cut -f1)
        log_success "OpenGauss backup completed, file size: $file_size"
    else
        log_error "OpenGauss backup file not found"
        return 1
    fi
}

# Backup MinIO data
backup_minio() {
    log_step "Starting MinIO data backup"

    # Get PV name
    log_info "Finding MinIO PV..."
    local pv_name=$(kubectl get pv -n euler-copilot | grep minio | awk '{print $1}')
    if [ -z "$pv_name" ]; then
        log_error "MinIO PV not found"
        return 1
    fi
    log_success "Found PV: $pv_name"

    # MinIO data directory
    local minio_storage_dir="/var/lib/rancher/k3s/storage/${pv_name}_euler-copilot_minio-storage/"

    # Check if source directory exists
    if [ ! -d "$minio_storage_dir" ]; then
        log_error "MinIO storage directory does not exist: $minio_storage_dir"
        return 1
    fi

    # Backup MinIO data
    log_info "Starting MinIO data backup..."
    cp -r "$minio_storage_dir"* "$MINIO_BACKUP_DIR"/
    check_command "MinIO data backup completed" "MinIO data backup failed"

    # Verify backup
    local source_count=$(find "$minio_storage_dir" -type f 2>/dev/null | wc -l)
    local backup_count=$(find "$MINIO_BACKUP_DIR" -type f 2>/dev/null | wc -l)

    log_info "Source file count: $source_count, Backup file count: $backup_count"

    if [ "$source_count" -eq "$backup_count" ]; then
        log_success "MinIO backup verification successful"
    else
        log_warning "File count mismatch, but backup completed"
    fi
}

# Show backup summary
show_backup_summary() {
    log_step "Backup Summary"

    echo -e "${CYAN}"
    echo "Backup Location: $BACKUP_BASE"
    echo "----------------------------------------"

    # MySQL backup information
    if [ -f "$MYSQL_BACKUP_DIR/mysql.sql" ]; then
        local mysql_size=$(du -h "$MYSQL_BACKUP_DIR/mysql.sql" | cut -f1)
        echo "MySQL:    $MYSQL_BACKUP_DIR/mysql.sql ($mysql_size)"
    else
        echo "MySQL:    Backup failed"
    fi

    # OpenGauss backup information
    if [ -f "$OPENGAUSS_BACKUP_DIR/opengauss.sql" ]; then
        local gauss_size=$(du -h "$OPENGAUSS_BACKUP_DIR/opengauss.sql" | cut -f1)
        echo "OpenGauss: $OPENGAUSS_BACKUP_DIR/opengauss.sql ($gauss_size)"
    else
        echo "OpenGauss: Backup failed"
    fi

    # MinIO backup information
    if [ -d "$MINIO_BACKUP_DIR" ]; then
        local minio_size=$(du -sh "$MINIO_BACKUP_DIR" 2>/dev/null | cut -f1 || echo "Unknown")
        local minio_count=$(find "$MINIO_BACKUP_DIR" -type f 2>/dev/null | wc -l)
        echo "MinIO:    $MINIO_BACKUP_DIR/ ($minio_size, $minio_count files)"
    else
        echo "MinIO:    Backup failed"
    fi
    echo -e "${NC}"
}

# Main function
main() {
    print_banner

    log_step "Starting data backup process"

    # Create backup directories
    create_backup_directories

    # Backup MySQL
    if backup_mysql; then
        log_success "MySQL backup successful"
    else
        log_error "MySQL backup failed"
    fi

    # Backup OpenGauss
    if backup_opengauss; then
        log_success "OpenGauss backup successful"
    else
        log_error "OpenGauss backup failed"
    fi

    # Backup MinIO
    if backup_minio; then
        log_success "MinIO backup successful"
    else
        log_error "MinIO backup failed"
    fi

    # Show backup summary
    show_backup_summary

    print_completion_banner
    log_success "Data backup process completed"
}

# Execute main function
main "$@"
