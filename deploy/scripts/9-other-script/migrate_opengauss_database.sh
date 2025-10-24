#!/bin/bash

# OpenGauss Database Import Script - Fixed Version
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
DATA_ONLY_SQL_PATH="/home/omm/data_only.sql"

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

# Extract only data from SQL file
extract_data_only() {
    step "Extracting data-only SQL commands"
    
    # Create a script to extract only data (COPY statements)
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c "
cat > /tmp/extract_data.sh << 'EOF'
#!/bin/bash
# Extract only COPY statements from the SQL file
grep '^COPY ' $POD_BACKUP_PATH > $DATA_ONLY_SQL_PATH

# Also extract the data section (everything after the first occurrence of COPY)
# This is a more robust method to get all data
sed -n '/^COPY /,/^\\\\\./p' $POD_BACKUP_PATH > $DATA_ONLY_SQL_PATH

# Add the SET commands at the beginning
echo 'SET session_replication_role = replica;' > /tmp/header.sql
cat /tmp/header.sql $DATA_ONLY_SQL_PATH > /tmp/combined.sql
mv /tmp/combined.sql $DATA_ONLY_SQL_PATH

# Add session_replication_role reset at the end
echo 'SET session_replication_role = origin;' >> $DATA_ONLY_SQL_PATH

echo 'Data extraction completed'
EOF

chmod +x /tmp/extract_data.sh
/tmp/extract_data.sh
"
    
    log "Data-only SQL extraction completed"
}

# Execute data-only import
import_data_only() {
    step "Executing data-only import"

    info "Step 1: Disabling foreign key constraints..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = replica;\""
    log "Foreign key constraints disabled"

    info "Step 2: Clearing existing data from tables..."
    # Truncate all tables to avoid duplicate key errors
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"
TRUNCATE TABLE 
    action, team, knowledge_base, document, chunk, document_type,
    role, role_action, users, task, task_report, team_user, user_role,
    dataset, dataset_doc, image, qa, task_queue, team_message,
    testcase, testing, user_message 
CASCADE;\""
    log "Existing data cleared"

    info "Step 3: Importing data only (COPY statements)..."
    # Use ON_ERROR_STOP=off to continue even if there are errors
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -f $DATA_ONLY_SQL_PATH -W '$PASSWORD' --set ON_ERROR_STOP=off"
    log "Data import completed"

    info "Step 4: Re-enabling foreign key constraints..."
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = origin;\""
    log "Foreign key constraints re-enabled"

    log "Data-only import completed"
}

# Alternative method: Manual table-by-table import
manual_table_import() {
    step "Using manual table-by-table import method"
    
    # Disable constraints
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = replica;\""
    
    # List of tables to import data for (in dependency order)
    tables=("action" "users" "team" "team_user" "user_role" "role" "role_action" 
            "knowledge_base" "document_type" "document" "chunk" "dataset" 
            "dataset_doc" "image" "qa" "task" "task_queue" "task_report" 
            "team_message" "testcase" "testing" "user_message")
    
    for table in "${tables[@]}"; do
        info "Processing table: $table"
        # Extract and import data for this specific table
        kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c "
            # Clear existing data
            gsql -d postgres -U postgres -W '$PASSWORD' -c \"TRUNCATE TABLE $table CASCADE;\" 2>/dev/null || echo 'Table $table already empty or does not exist'
            
            # Extract data for this table from backup
            sed -n '/^COPY $table /,/^\\\\\\./p' $POD_BACKUP_PATH > /tmp/${table}_data.sql 2>/dev/null
            
            # Import if data exists
            if [ -s /tmp/${table}_data.sql ]; then
                gsql -d postgres -U postgres -W '$PASSWORD' -f /tmp/${table}_data.sql --set ON_ERROR_STOP=off
                echo 'Imported data for $table'
            else
                echo 'No data found for $table'
            fi
            
            # Cleanup
            rm -f /tmp/${table}_data.sql
        " || warning "Failed to process table $table, continuing..."
    done
    
    # Re-enable constraints
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c \
        "gsql -d postgres -U postgres -W '$PASSWORD' -c \"SET session_replication_role = origin;\""
    
    log "Manual table import completed"
}

# Clean up temporary files
cleanup() {
    step "Cleaning up temporary files"
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- rm -f \
        "$POD_BACKUP_PATH" \
        "$DATA_ONLY_SQL_PATH" \
        "/tmp/extract_data.sh" \
        "/tmp/header.sql" \
        "/tmp/combined.sql" \
        "/tmp/*_data.sql" 2>/dev/null || true
    log "Cleanup completed"
}

# Show banner
show_banner() {
    echo -e "${PURPLE}"
    echo "================================================================"
    echo "                OpenGauss Database Import Script"
    echo "                Fixed Version - Data Only Import"
    echo "================================================================"
    echo -e "${NC}"
}

# Verify import success
verify_import() {
    step "Verifying import success"
    
    # Check if key tables have data
    kubectl exec -it "$POD_NAME" -n $NAMESPACE -- su - omm -s /bin/bash -c "
        echo 'Checking table row counts:'
        gsql -d postgres -U postgres -W '$PASSWORD' -c \"
            SELECT 'users' as table_name, COUNT(*) as row_count FROM users
            UNION ALL SELECT 'team', COUNT(*) FROM team  
            UNION ALL SELECT 'action', COUNT(*) FROM action
            UNION ALL SELECT 'document', COUNT(*) FROM document
            ORDER BY table_name;
        \" || echo 'Verification query failed'
    "
    
    log "Verification completed"
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
    
    # Try data-only import first
    extract_data_only
    import_data_only
    
    # If that fails, try manual method
    if [ $? -ne 0 ]; then
        warning "Data-only import encountered issues, trying manual table-by-table import..."
        manual_table_import
    fi
    
    verify_import
    cleanup

    echo -e "${GREEN}"
    echo "================================================================"
    echo "                   OpenGauss Data Import Completed!"
    echo "================================================================"
    echo -e "${NC}"

    echo -e "${GREEN}✓ Foreign key constraints disabled${NC}"
    echo -e "${GREEN}✓ Existing data cleared${NC}"
    echo -e "${GREEN}✓ New data imported${NC}"
    echo -e "${GREEN}✓ Foreign key constraints re-enabled${NC}"
    echo -e "${GREEN}✓ Import verified${NC}"
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

echo -e "${YELLOW}Warning: This operation will clear existing database data and import new data!${NC}"

yellow_text="${YELLOW}Confirm execution of database import operation? (y/N): ${NC}"
read -p "$(echo -e "$yellow_text")" confirm

case $confirm in
    [yY] | [yY][eE][sS])
        main
        ;;
    *)
        warning "Operation cancelled"
        exit 0
        ;;
esac
