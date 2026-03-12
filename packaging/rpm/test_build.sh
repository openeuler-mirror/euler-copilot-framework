#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) Huawei Technologies Co., Ltd. 2024-2026.
#
# witty-framework-lite RPM 测试构建脚本
#
# 在本地（或 VM）模拟 rpmbuild 流程，用于验证 spec 正确性。
# 生成的 RPM 位于 ~/rpmbuild/RPMS/ 下。
#
# 使用方法:
#   ./packaging/rpm/test_build.sh                        # 完整构建（两个子包）
#   ./packaging/rpm/test_build.sh --lite-only             # 仅构建 witty-framework-lite
#   ./packaging/rpm/test_build.sh --mcp-only              # 仅构建 witty-mcp-manager
#   ./packaging/rpm/test_build.sh --no-deps               # 跳过 BuildRequires 检查
#   ./packaging/rpm/test_build.sh --source-only           # 仅生成 SRPM
#
# 前置条件:
#   - rpm-build 已安装
#   - 构建 witty-mcp-manager 需要: gcc gcc-c++ patchelf python3-nuitka 等
#   - 建议在 openEuler 系统上运行

set -euo pipefail

# ── 常量 ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC_FILE="${SCRIPT_DIR}/euler-copilot-framework.spec"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 从 spec 文件中提取版本信息
PKG_NAME=$(grep '^Name:' "${SPEC_FILE}" | awk '{print $2}')
PKG_VERSION=$(grep '^Version:' "${SPEC_FILE}" | awk '{print $2}')
TARBALL_NAME="${PKG_NAME}-${PKG_VERSION}"

# rpmbuild 根目录
RPM_TOPDIR="${RPM_TOPDIR:-${HOME}/rpmbuild}"

# ── 参数解析 ──────────────────────────────────────────────────────
BUILD_TARGET="all"         # all | lite | mcp | srpm
SKIP_DEPS=0
VERBOSE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --lite-only)    BUILD_TARGET="lite";  shift ;;
        --mcp-only)     BUILD_TARGET="mcp";   shift ;;
        --source-only)  BUILD_TARGET="srpm";  shift ;;
        --no-deps)      SKIP_DEPS=1;          shift ;;
        --verbose|-v)   VERBOSE=1;            shift ;;
        --topdir)       RPM_TOPDIR="$2";      shift 2 ;;
        -h|--help)
            cat <<'EOF'
用法: test_build.sh [选项]

选项:
  --lite-only       仅构建 witty-framework-lite 子包
  --mcp-only        仅构建 witty-mcp-manager 子包
  --source-only     仅生成源码 RPM (SRPM)
  --no-deps         跳过 BuildRequires 依赖检查
  --topdir DIR      自定义 rpmbuild 根目录 (默认: ~/rpmbuild)
  --verbose, -v     显示详细 rpmbuild 输出
  -h, --help        显示帮助
EOF
            exit 0
            ;;
        *)
            echo "未知选项: $1" >&2
            exit 1
            ;;
    esac
done

# ── 颜色与输出 ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }

# ── 前置检查 ──────────────────────────────────────────────────────
info "=== Witty Framework RPM 测试构建 ==="
info "包名:     ${PKG_NAME}"
info "版本:     ${PKG_VERSION}"
info "构建目标: ${BUILD_TARGET}"
info "Spec:     ${SPEC_FILE}"
echo ""

# 检查 rpmbuild 命令
command -v rpmbuild >/dev/null 2>&1 || fail "rpmbuild 未找到。请安装: dnf install rpm-build"
command -v rpmspec  >/dev/null 2>&1 || fail "rpmspec 未找到。请安装: dnf install rpm-build"

# 验证 spec 语法
info "验证 spec 语法..."
if rpmspec --parse "${SPEC_FILE}" >/dev/null 2>&1; then
    ok "Spec 语法检查通过"
else
    fail "Spec 语法检查失败，请修正 ${SPEC_FILE}"
fi

# 检查 BuildRequires（可选）
if [[ "${SKIP_DEPS}" -eq 0 ]]; then
    info "检查 BuildRequires 依赖..."
    MISSING_DEPS=()

    while IFS= read -r dep; do
        # 提取包名（去除版本约束）
        dep_name=$(echo "$dep" | awk '{print $1}')
        if ! rpm -q "${dep_name}" >/dev/null 2>&1; then
            MISSING_DEPS+=("${dep_name}")
        fi
    done < <(rpmspec --query --buildrequires "${SPEC_FILE}" 2>/dev/null)

    if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
        warn "以下 BuildRequires 缺失:"
        for dep in "${MISSING_DEPS[@]}"; do
            echo "  - ${dep}"
        done
        warn "可使用 --no-deps 跳过依赖检查，或安装: dnf install ${MISSING_DEPS[*]}"
        echo ""
        # 非致命——rpmbuild --nodeps 也能继续
    else
        ok "所有 BuildRequires 已满足"
    fi
fi

# ── 初始化 rpmbuild 目录 ─────────────────────────────────────────
info "初始化 rpmbuild 目录: ${RPM_TOPDIR}"
mkdir -p "${RPM_TOPDIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# ── 生成源码 tarball ─────────────────────────────────────────────
info "打包源码 tarball: ${TARBALL_NAME}.tar.gz"

TARBALL_PATH="${RPM_TOPDIR}/SOURCES/${TARBALL_NAME}.tar.gz"

# 创建临时目录用于 tarball 根
TMPDIR_TAR=$(mktemp -d)
trap 'rm -rf "${TMPDIR_TAR}"' EXIT

STAGE_DIR="${TMPDIR_TAR}/${TARBALL_NAME}"
mkdir -p "${STAGE_DIR}"

# 定义需要包含的文件/目录
INCLUDES=(
    apps
    mcp_center
    data
    docs
    witty_mcp_manager
    LICENSE
    README.md
    pyproject.toml
)

for item in "${INCLUDES[@]}"; do
    src="${PROJECT_ROOT}/${item}"
    if [[ -e "$src" ]]; then
        cp -a "$src" "${STAGE_DIR}/"
    else
        warn "源文件/目录不存在，跳过: ${item}"
    fi
done

# 清理不需要的文件
find "${STAGE_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_DIR}" -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_DIR}" -type d -name '.mypy_cache' -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_DIR}" -type d -name '.ruff_cache' -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_DIR}" -type d -name '.venv' -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_DIR}" -name '*.pyc' -delete 2>/dev/null || true
rm -rf "${STAGE_DIR}/witty_mcp_manager/dist" 2>/dev/null || true

# 生成 tarball
tar -czf "${TARBALL_PATH}" -C "${TMPDIR_TAR}" "${TARBALL_NAME}"
ok "Tarball 已生成: ${TARBALL_PATH} ($(du -h "${TARBALL_PATH}" | cut -f1))"

# 复制 spec 文件
cp "${SPEC_FILE}" "${RPM_TOPDIR}/SPECS/"
ok "Spec 已复制到 ${RPM_TOPDIR}/SPECS/"

# ── 执行 rpmbuild ────────────────────────────────────────────────
RPMBUILD_OPTS=(
    --define "_topdir ${RPM_TOPDIR}"
)

# 跳过依赖检查
if [[ "${SKIP_DEPS}" -eq 1 ]]; then
    RPMBUILD_OPTS+=("--nodeps")
fi

# 根据构建目标确定 rpmbuild 参数
SPEC_IN_TOPDIR="${RPM_TOPDIR}/SPECS/euler-copilot-framework.spec"

case "${BUILD_TARGET}" in
    srpm)
        info "生成 SRPM..."
        rpmbuild "${RPMBUILD_OPTS[@]}" -bs "${SPEC_IN_TOPDIR}"
        ok "SRPM 已生成:"
        find "${RPM_TOPDIR}/SRPMS" -name "*.src.rpm" -newer "${TARBALL_PATH}" | while read -r f; do
            echo "  ${f}"
        done
        ;;
    lite)
        info "构建 witty-framework-lite（主包）..."
        if [[ "${VERBOSE}" -eq 1 ]]; then
            rpmbuild "${RPMBUILD_OPTS[@]}" -bb "${SPEC_IN_TOPDIR}" \
                --define '_without_mcp 1' 2>&1 || \
            rpmbuild "${RPMBUILD_OPTS[@]}" -bb "${SPEC_IN_TOPDIR}" 2>&1
        else
            rpmbuild "${RPMBUILD_OPTS[@]}" -bb "${SPEC_IN_TOPDIR}" 2>&1 | \
                tail -20
        fi
        ;;
    mcp)
        info "构建 witty-mcp-manager..."
        if [[ "${VERBOSE}" -eq 1 ]]; then
            rpmbuild "${RPMBUILD_OPTS[@]}" -bb "${SPEC_IN_TOPDIR}" 2>&1
        else
            rpmbuild "${RPMBUILD_OPTS[@]}" -bb "${SPEC_IN_TOPDIR}" 2>&1 | \
                tail -20
        fi
        ;;
    all)
        info "完整构建（SRPM + 所有二进制 RPM）..."
        if [[ "${VERBOSE}" -eq 1 ]]; then
            rpmbuild "${RPMBUILD_OPTS[@]}" -ba "${SPEC_IN_TOPDIR}" 2>&1
        else
            rpmbuild "${RPMBUILD_OPTS[@]}" -ba "${SPEC_IN_TOPDIR}" 2>&1 | \
                tail -30
        fi
        ;;
esac

BUILD_RC=$?

echo ""
if [[ ${BUILD_RC} -eq 0 ]]; then
    ok "=== 构建成功！ ==="
    echo ""
    info "生成的 RPM:"
    find "${RPM_TOPDIR}/RPMS" "${RPM_TOPDIR}/SRPMS" \
        -name "*.rpm" -newer "${TARBALL_PATH}" 2>/dev/null | sort | while read -r f; do
        SIZE=$(du -h "$f" | cut -f1)
        echo "  ${f}  (${SIZE})"
    done
    echo ""
    info "安装测试:"
    echo "  sudo rpm -ivh --nodeps ${RPM_TOPDIR}/RPMS/*/euler-copilot-framework-*.rpm"
    echo "  sudo rpm -ivh --nodeps ${RPM_TOPDIR}/RPMS/*/witty-mcp-manager-*.rpm"
    echo ""
    info "查询包内容:"
    echo "  rpm -qlp ${RPM_TOPDIR}/RPMS/*/euler-copilot-framework-*.rpm"
    echo "  rpm -qlp ${RPM_TOPDIR}/RPMS/*/witty-mcp-manager-*.rpm"
else
    fail "=== 构建失败 (exit code: ${BUILD_RC}) ==="
fi

exit ${BUILD_RC}
