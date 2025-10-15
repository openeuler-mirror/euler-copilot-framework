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

# Log functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${PURPLE}[STEP]${NC} $1"; }

# Global variables
PV_NAME=""
POD_NAME=""
STORAGE_DIR=""
NEW_POD_NAME=""
MINIO_PASSWORD=""
MINIO_ROOT_USER="minioadmin"
MINIO_HOST=""
MINIO_PORT=""
source_dir="/home/dump/minio"

# Print banner
print_banner() {
    echo -e "${GREEN}"
    echo "===================================================================="
    echo "                  MINIO Data Import Script"
    echo "                 Euler Copilot Project Specific"
    echo "===================================================================="
    echo -e "${NC}"
}

print_completion_banner() {
    echo -e "${GREEN}"
    echo "===================================================================="
    echo "                  MINIO Data Import Completed!"
    echo "===================================================================="
    echo -e "${NC}"
}

# User confirmation
confirm_execution() {
    echo -e "${YELLOW}Warning: This operation will clear existing MinIO data and import new data!${NC}"
    read -p "Confirm execution of MinIO data import operation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled"
        exit 0
    fi
}

# Remove color codes and special characters
clean_output() {
    echo "$1" | sed -r "s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g" | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
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

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check if kubectl is available
    kubectl cluster-info &> /dev/null
    check_command "kubectl connection normal" "Unable to connect to Kubernetes cluster"

    # Check if namespace exists
    if ! kubectl get namespace euler-copilot &> /dev/null; then
        log_error "Namespace euler-copilot does not exist"
        exit 1
    fi
    log_success "Namespace euler-copilot exists"
}

# Get Kubernetes resources
get_kubernetes_resources() {
    log_step "Getting Kubernetes resource information..."

    # Get PV name
    PV_NAME=$(kubectl get pv -n euler-copilot | grep minio | awk '{print $1}')
    if [ -z "$PV_NAME" ]; then
        log_error "No MinIO PV found"
        exit 1
    fi
    log_info "PV name: $PV_NAME"

    # Get Pod name
    POD_NAME=$(kubectl get pods -n euler-copilot | grep minio | grep Running | awk '{print $1}')
    POD_NAME=$(clean_output "$POD_NAME")
    if [ -z "$POD_NAME" ]; then
        log_error "No running MinIO Pod found"
        exit 1
    fi
    log_info "Pod name: $POD_NAME"

    # Set storage directory
    STORAGE_DIR="/var/lib/rancher/k3s/storage/${PV_NAME}_euler-copilot_minio-storage/"
    log_info "Storage directory: $STORAGE_DIR"
}

# Copy data
copy_data() {
    log_step "Copying data..."

    if [ -d "$source_dir" ]; then
        # Check source data
        local source_count=$(find "$source_dir" -type f 2>/dev/null | wc -l)
        if [ "$source_count" -eq 0 ]; then
            log_warning "Source directory is empty, skipping copy"
            return 0
        fi

        log_info "Source directory file count: $source_count"
        cp -r "$source_dir"/* "$STORAGE_DIR"
        check_command "Data copy completed" "Data copy failed"

        # Verify copy result
        local new_count=$(find "$STORAGE_DIR" -type f 2>/dev/null | wc -l)
        log_info "File count after copy: $new_count"

        if [ "$source_count" -eq "$new_count" ]; then
            log_success "File count verification successful"
        else
            log_warning "File count mismatch: source=$source_count, target=$new_count"
        fi
    else
        log_error "Source directory $source_dir does not exist"
        exit 1
    fi
}

# Restart Pod
restart_pod() {
    log_step "Restarting Pod..."

    kubectl delete pod "$POD_NAME" -n euler-copilot
    check_command "Pod deletion command executed successfully" "Pod deletion failed"

    # Wait for Pod restart
    log_info "Waiting for Pod restart..."
    local timeout=60
    local counter=0

    while [ $counter -lt $timeout ]; do
        NEW_POD_NAME=$(kubectl get pods -n euler-copilot | grep minio | grep Running | awk '{print $1}')
        NEW_POD_NAME=$(clean_output "$NEW_POD_NAME")

        if [ -n "$NEW_POD_NAME" ]; then
            log_success "Pod restarted successfully: $NEW_POD_NAME"
            return 0
        fi

        counter=$((counter + 5))
        sleep 5
        echo -n "."
    done

    log_error "Pod did not restart within specified time"
    return 1
}

# Get MinIO configuration
get_minio_config() {
    log_step "Getting MinIO configuration..."

    MINIO_PASSWORD=$(kubectl get secret euler-copilot-database -n euler-copilot -o jsonpath='{.data.minio-password}' 2>/dev/null | base64 --decode)
    if [ $? -ne 0 ] || [ -z "$MINIO_PASSWORD" ]; then
        log_error "Failed to get MinIO password"
        exit 1
    fi

    MINIO_HOST=$(kubectl get svc -n euler-copilot | grep minio-service | awk '{print $3}')
    MINIO_PORT=$(kubectl get svc -n euler-copilot | grep minio-service | awk '{split($5, a, "/"); print a[1]}')

    log_info "MinIO configuration:"
    log_info "  Host: $MINIO_HOST"
    log_info "  Port: $MINIO_PORT"
    log_info "  User: $MINIO_ROOT_USER"
}

# Verify MinIO data
verify_minio_data() {
    log_step "Verifying MinIO data..."

    # Set up mc client
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc alias set myminio "http://${MINIO_HOST}:${MINIO_PORT}" "$MINIO_ROOT_USER" "$MINIO_PASSWORD"
    check_command "MinIO client setup successful" "MinIO client setup failed"

    # List buckets
    log_info "MinIO Buckets list:"
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc ls myminio
    if [ $? -eq 0 ]; then
        log_success "MinIO connection normal"
    else
        log_error "MinIO connection failed"
        exit 1
    fi

    # Check specific bucket content
    log_info "Checking witchaind-doc bucket:"
    kubectl exec -it "$NEW_POD_NAME" -n euler-copilot -- mc ls myminio/witchaind-doc
    if [ $? -eq 0 ]; then
        log_success "witchaind-doc bucket access successful"
    else
        log_warning "witchaind-doc bucket does not exist or is empty"
    fi
}

# Main function
main() {
    print_banner
    confirm_execution

    # Execute each step
    check_prerequisites
    get_kubernetes_resources
    copy_data
    restart_pod
    get_minio_config
    verify_minio_data

    print_completion_banner
    log_success "MINIO data import process fully completed"
    log_info "Please verify if business functions are working normally"
}

# Execute main function
main "$@"
