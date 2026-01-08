#!/bin/bash

# OpenGauss Database Import Script - Fixed Version
# Description: Used for Euler Copilot project database data import


NAMESPACE="euler-copilot"
SECRET_NAME="euler-copilot-database"
PASSWORD_KEY="gauss-password"
ACTION=""  # 不再设置默认值，通过参数检查

POD_NAME=""
DB_HOST=""
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="postgres"
PASSWORD=""

red() { echo -e "\033[31m[ERROR] $1\033[0m"; }
green() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
blue() { echo -e "\033[34m[INFO] $1\033[0m"; }
yellow() { echo -e "\033[33m[WARNING] $1\033[0m"; }

error_exit() {
    red "$1"
    exit 1
}

# 检查命令是否可用
check_command() {
    if ! command -v $1 &> /dev/null; then
        error_exit "命令 $1 未找到，请先安装"
    fi
}

# 检查kubectl连接
check_kubectl() {
    blue "检查kubectl连接..."
    if ! kubectl cluster-info &> /dev/null; then
        error_exit "无法连接到Kubernetes集群，请检查kubectl配置"
    fi
    green "kubectl连接正常"
}

# 获取rag的pod名称
get_pod_name() {
    if [ -n "$POD_NAME" ]; then
        green "使用指定的pod: $POD_NAME"
        return 0
    fi

    blue "查找rag的pod..."
    POD_NAME=$(kubectl get pod -n $NAMESPACE 2>/dev/null | grep rag-deploy | grep Running | awk '{print $1}')
    green "pod名称获取成功"
}

# 获取数据库密码
get_db_password() {
    blue "获取数据库密码..."
    PASSWORD=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath="{.data.$PASSWORD_KEY}" 2>/dev/null | base64 --decode)

    if [ -z "$PASSWORD" ]; then
        error_exit "无法获取数据库密码，请检查secret是否存在"
    fi
    green "密码获取成功"
}

# 获取数据库主机地址
get_db_host() {
    blue "获取数据库服务地址..."
    DB_HOST=$(kubectl get svc -n $NAMESPACE 2>/dev/null | grep opengauss | awk '{print $3}')

    if [ -z "$DB_HOST" ]; then
        error_exit "未找到opengauss服务"
    fi

    green "数据库地址: $DB_HOST"
}

# 显示数据库配置信息
show_db_config() {
    blue "数据库配置信息:"
    echo "================================="
    echo "  Pod名称:     $POD_NAME"
    echo "  数据库地址:   $DB_HOST"
    echo "  端口:        $DB_PORT"
    echo "  用户名:      $DB_USER"
    echo "  数据库名:    $DB_NAME"
    echo "  操作类型:    $ACTION"
    echo "  密码:        ********"
    echo "================================="

    read -p "是否继续执行? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        yellow "操作已取消"
        exit 0
    fi
}

# 在pod中执行命令
execute_in_pod() {
    blue "在pod $POD_NAME 中执行$ACTION操作..."
    # 构建Python命令
    local python_cmd=""
    if [ "$ACTION" = "load" ]; then
        python_cmd="mv /home/tmp /home/sql_dump_load_tool && python3 main.py --action load --db-type opengauss --db-host '$DB_HOST' --db-port '$DB_PORT' --db-user '$DB_USER' --db-password '$PASSWORD' --db-name '$DB_NAME'"
    elif [ "$ACTION" = "dump" ]; then
        python_cmd="python3 main.py --action dump --db-type opengauss --db-host '$DB_HOST' --db-port '$DB_PORT' --db-user '$DB_USER' --db-password '$PASSWORD' --db-name '$DB_NAME'"
    else
        error_exit "未知的操作类型: $ACTION"
    fi

    # 直接在kubectl exec中执行命令，确保实时输出
    blue "开始执行远程命令..."
    echo "================================="

    kubectl exec -it $POD_NAME -n $NAMESPACE -- /bin/bash -c "
echo '开始配置yum源...'
sed -i 's|repo.openeuler.org|repo.huaweicloud.com/openeuler|g' /etc/yum.repos.d/openEuler.repo
sed -i 's|\$basearch/aarch64|aarch64|g' /etc/yum.repos.d/openEuler.repo
sed -i 's|\$releasever|24.03-LTS-SP2|g' /etc/yum.repos.d/openEuler.repo
sed -i '/metalink/d' /etc/yum.repos.d/openEuler.repo
sed -i '/metadata_expire/d' /etc/yum.repos.d/openEuler.repo
yum clean all
yum makecache
echo 'yum源配置完成'

echo '安装git...'
yum -y install git
echo 'git安装完成'

echo '克隆仓库...'
if [ -d '/home/sql_dump_load_tool' ]; then
    echo '仓库已存在，跳过克隆'
    rm -rf /home/sql_dump_load_tool/tmp
    echo '更新仓库...'
    git pull
else
    git clone https://gitcode.com/zxstty/sql_dump_load_tool /home/sql_dump_load_tool
    echo '仓库克隆完成'
fi

# 进入目录
cd /home/sql_dump_load_tool

echo '开始执行${ACTION}操作...'
echo '================================='
# 确保Python输出不会被缓冲
export PYTHONUNBUFFERED=1
# 执行Python脚本
$python_cmd
"

    local result=$?

    if [ $result -eq 0 ]; then
        green "${ACTION}操作执行完成！"
    else
        red "${ACTION}操作执行失败，退出码: $result"
        return $result
    fi
}

main() {
    if [ -z "$ACTION" ]; then
        red "必须指定操作类型: --action dump 或 --action load"
        show_help
        exit 1
    fi

    if [ "$ACTION" != "dump" ] && [ "$ACTION" != "load" ]; then
        red "操作类型必须是 'dump' 或 'load'"
        show_help
        exit 1
    fi

    blue "开始执行数据${ACTION}脚本"
    echo "================================="

    check_command "kubectl"
    check_command "base64"

    check_kubectl

    get_pod_name
    get_db_password
    get_db_host

    show_db_config
    # 如果是load操作，先拷贝宿主机/home/dump/opengauss的数据至openGauss的POD中
    if [ "$ACTION" = "load" ]; then
        kubectl cp /home/dump/opengauss ${POD_NAME}:/home/tmp -n $NAMESPACE
    fi

    # 在pod中执行命令
    execute_in_pod
    if [ "$ACTION" = "dump" ]; then
        kubectl cp ${POD_NAME}:/home/sql_dump_load_tool/tmp /home/dump/opengauss -n $NAMESPACE
        # 显示结果
        echo "检查文件..."
        ls -l /home/dump/opengauss
    fi
    green "所有操作已完成！"
}


# 仅获取配置信息，不执行
get_config_only() {
    blue "仅获取配置信息"
    get_pod_name
    get_db_password
    get_db_host
    show_db_config
}

# 测试数据库连接
test_db_connection() {
    blue "测试数据库连接..."
    get_pod_name
    get_db_password
    get_db_host

    local test_cmd=$(cat <<EOF
echo "测试数据库连接..."
export PYTHONUNBUFFERED=1
timeout 10 python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='$DB_HOST',
        port='$DB_PORT',
        user='$DB_USER',
        password='$PASSWORD',
        database='$DB_NAME'
    )
    print('数据库连接成功')
    conn.close()
except Exception as e:
    print(f'数据库连接失败: {e}')
    exit(1)
"
EOF
    )

    blue "尝试连接到数据库..."
    kubectl exec $POD_NAME -n $NAMESPACE -- /bin/bash -c "$test_cmd"
}

# 仅清空表数据（不执行导入）
clear_data_only() {
    blue "仅清空数据库表数据"
    get_pod_name
    get_db_password
    get_db_host
    show_db_config
}


# 显示使用帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help          显示此帮助信息"
    echo "  -a, --action        指定操作类型 (dump 或 load)"
    echo "  -c, --config        仅获取配置信息，不执行"
    echo "  -t, --test          测试数据库连接"
    echo "  -d, --clear-only    仅清空表数据，不执行导入"
    echo "  -n, --namespace     指定命名空间（默认: euler-copilot）"
    echo "  -s, --secret        指定secret名称"
    echo "  -p, --pod           指定pod名称（跳过自动查找）"
    echo ""
    echo "示例:"
    echo "  $0 --action load    执行数据导入"
    echo "  $0 --action dump    执行数据导出"
    echo "  $0 --config         仅显示配置信息"
    echo "  $0 --test           测试数据库连接"
    echo "  $0 --clear-only     仅清空表数据"
    echo "  $0 --namespace myns --secret my-secret"
}

# ============================================
# 参数解析
# ============================================
parse_args() {
    # 如果没有参数，显示帮助信息
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    # 存储其他参数
    local other_args=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -a|--action)
                ACTION="$2"
                shift 2
                ;;
            -c|--config)
                get_config_only
                exit 0
                ;;
            -t|--test)
                test_db_connection
                exit 0
                ;;
            -d|--clear-only)
                clear_data_only
                exit 0
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -s|--secret)
                SECRET_NAME="$2"
                shift 2
                ;;
            -p|--pod)
                POD_NAME="$2"
                shift 2
                ;;
            *)
                # 收集其他参数（如果需要的话）
                other_args="$other_args $1"
                shift
                ;;
        esac
    done

    # 如果指定了action，执行主流程
    if [ -n "$ACTION" ]; then
        main
    else
        red "必须指定操作类型: --action dump 或 --action load"
        show_help
        exit 1
    fi
}

# 解析参数并执行
parse_args "$@"