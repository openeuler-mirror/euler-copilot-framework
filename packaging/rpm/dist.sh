#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) Huawei Technologies Co., Ltd. 2024-2026.
#
# 发布归档脚本
#
# 将当前分支最新提交的源码打包为 RPM Source0 tarball，
# 并连同最新 spec 文件一起输出到项目根目录下的 ./dist。
#
# 使用方法:
#   ./packaging/rpm/dist.sh                # 正常归档（基于 git HEAD）
#   ./packaging/rpm/dist.sh --with-dirty   # 包含未提交的本地修改
#   ./packaging/rpm/dist.sh --output DIR   # 自定义输出目录（默认: <项目根>/dist）
#   ./packaging/rpm/dist.sh --tag          # 在 git 中创建版本标签
#
# 输出:
#   dist/
#     euler-copilot-framework-<version>.tar.gz   RPM Source0 tarball
#     euler-copilot-framework.spec               RPM spec 文件

set -euo pipefail

# ── 路径常量 ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC_FILE="${SCRIPT_DIR}/euler-copilot-framework.spec"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── 从 spec 读取元数据 ─────────────────────────────────────────────
PKG_NAME=$(    grep '^Name:'    "${SPEC_FILE}" | awk '{print $2}')
PKG_VERSION=$( grep '^Version:' "${SPEC_FILE}" | awk '{print $2}')
PKG_RELEASE=$( grep '^Release:' "${SPEC_FILE}" | awk '{print $2}')
TARBALL_STEM="${PKG_NAME}-${PKG_VERSION}"

# ── 参数解析 ───────────────────────────────────────────────────────
OUTPUT_DIR="${PROJECT_ROOT}/dist"
WITH_DIRTY=0
CREATE_TAG=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-dirty)  WITH_DIRTY=1;             shift ;;
        --tag)         CREATE_TAG=1;             shift ;;
        --output)      OUTPUT_DIR="$2";          shift 2 ;;
        -h|--help)
            cat <<'EOF'
用法: dist.sh [选项]

选项:
  --with-dirty      包含工作区中未提交的本地修改（默认仅归档 HEAD）
  --tag             成功后创建 git 版本标签 v<version>-<release>
  --output DIR      自定义输出目录（默认: <项目根>/dist）
  -h, --help        显示此帮助并退出
EOF
            exit 0
            ;;
        *)
            echo "未知选项: $1" >&2
            exit 1
            ;;
    esac
done

# ── 颜色输出 ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }

# ── 前置检查 ───────────────────────────────────────────────────────
info "=== Witty Framework 发布归档 ==="
info "包名:    ${PKG_NAME}"
info "版本:    ${PKG_VERSION}-${PKG_RELEASE}"
info "Spec:    ${SPEC_FILE}"
echo ""

command -v git >/dev/null 2>&1 || fail "未找到 git，请先安装 git"

# 确认当前目录在 git 仓库内
git -C "${PROJECT_ROOT}" rev-parse --git-dir >/dev/null 2>&1 \
    || fail "${PROJECT_ROOT} 不是 git 仓库"

BRANCH=$(git -C "${PROJECT_ROOT}" rev-parse --abbrev-ref HEAD)
COMMIT=$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)
COMMIT_FULL=$(git -C "${PROJECT_ROOT}" rev-parse HEAD)
COMMIT_DATE=$(git -C "${PROJECT_ROOT}" log -1 --format='%ci' HEAD)

info "分支:    ${BRANCH}"
info "提交:    ${COMMIT}  (${COMMIT_DATE})"
echo ""

# 检查未提交修改
DIRTY_FILES=""
if ! git -C "${PROJECT_ROOT}" diff --quiet HEAD; then
    DIRTY_FILES=$(git -C "${PROJECT_ROOT}" diff --name-only HEAD | head -20)
fi
if [[ -n "${DIRTY_FILES}" ]]; then
    warn "工作区存在未提交的修改:"
    echo "${DIRTY_FILES}" | while IFS= read -r f; do echo "  M  $f"; done
    echo ""
    if [[ "${WITH_DIRTY}" -eq 0 ]]; then
        warn "默认仅归档已提交内容（git HEAD）。"
        warn "如需包含本地修改，请使用 --with-dirty 选项。"
        echo ""
    else
        warn "已启用 --with-dirty，将包含本地未提交修改。"
        echo ""
    fi
fi

# ── 创建输出目录 ───────────────────────────────────────────────────
mkdir -p "${OUTPUT_DIR}"
TARBALL="${OUTPUT_DIR}/${TARBALL_STEM}.tar.gz"

# ── 生成源码 tarball ───────────────────────────────────────────────
# 需要打包的顶层路径（与 spec %install 段保持一致）
SOURCE_PATHS=(
    apps
    mcp_center
    data
    docs
    witty_mcp_manager
    LICENSE
    README.md
    pyproject.toml
)

info "生成源码 tarball: ${TARBALL_STEM}.tar.gz"

if [[ "${WITH_DIRTY}" -eq 1 ]]; then
    # ── 包含未提交修改：使用临时暂存目录 ────────────────────────────
    TMPDIR_TAR=$(mktemp -d)
    trap 'rm -rf "${TMPDIR_TAR}"' EXIT

    STAGE_DIR="${TMPDIR_TAR}/${TARBALL_STEM}"
    mkdir -p "${STAGE_DIR}"

    for item in "${SOURCE_PATHS[@]}"; do
        src="${PROJECT_ROOT}/${item}"
        if [[ -e "${src}" ]]; then
            cp -a "${src}" "${STAGE_DIR}/"
        else
            warn "路径不存在，跳过: ${item}"
        fi
    done

    # 清理构建产物
    find "${STAGE_DIR}" -type d -name '__pycache__'   -exec rm -rf {} + 2>/dev/null || true
    find "${STAGE_DIR}" -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
    find "${STAGE_DIR}" -type d -name '.mypy_cache'   -exec rm -rf {} + 2>/dev/null || true
    find "${STAGE_DIR}" -type d -name '.ruff_cache'   -exec rm -rf {} + 2>/dev/null || true
    find "${STAGE_DIR}" -type d -name '.venv'         -exec rm -rf {} + 2>/dev/null || true
    find "${STAGE_DIR}" -name '*.pyc'                 -delete       2>/dev/null || true
    rm -rf "${STAGE_DIR}/witty_mcp_manager/dist"                    2>/dev/null || true

    tar -czf "${TARBALL}" -C "${TMPDIR_TAR}" "${TARBALL_STEM}"
else
    # ── 仅已提交内容：使用 git archive（干净、可复现）──────────────
    # 构建 git archive 的 pathspec 参数（过滤不存在的路径）
    ARCHIVE_PATHS=()
    for item in "${SOURCE_PATHS[@]}"; do
        if git -C "${PROJECT_ROOT}" ls-files --error-unmatch "${item}" \
               >/dev/null 2>&1 \
           || git -C "${PROJECT_ROOT}" ls-tree --name-only HEAD "${item}" \
               >/dev/null 2>&1; then
            ARCHIVE_PATHS+=("${item}")
        else
            warn "git 中未追踪，跳过: ${item}"
        fi
    done

    git -C "${PROJECT_ROOT}" archive \
        --format=tar.gz \
        --prefix="${TARBALL_STEM}/" \
        HEAD \
        -- "${ARCHIVE_PATHS[@]}" \
        > "${TARBALL}"
fi

TARBALL_SIZE=$(du -sh "${TARBALL}" | cut -f1)
ok "Tarball 已生成: $(basename "${TARBALL}")  (${TARBALL_SIZE})"

# ── 复制 spec 文件 ─────────────────────────────────────────────────
SPEC_DST="${OUTPUT_DIR}/$(basename "${SPEC_FILE}")"
cp "${SPEC_FILE}" "${SPEC_DST}"
ok "Spec 已复制:    $(basename "${SPEC_DST}")"

# ── 写入版本元数据文件 ─────────────────────────────────────────────
META_FILE="${OUTPUT_DIR}/dist-info.txt"
cat > "${META_FILE}" <<EOF
package:      ${PKG_NAME}
version:      ${PKG_VERSION}
release:      ${PKG_RELEASE}
branch:       ${BRANCH}
commit:       ${COMMIT_FULL}
commit_short: ${COMMIT}
commit_date:  ${COMMIT_DATE}
with_dirty:   ${WITH_DIRTY}
tarball:      ${TARBALL_STEM}.tar.gz
tarball_size: ${TARBALL_SIZE}
built_at:     $(date -u '+%Y-%m-%dT%H:%M:%SZ')
EOF
ok "元数据已写入:  dist-info.txt"

# ── 可选：创建 git 标签 ────────────────────────────────────────────
if [[ "${CREATE_TAG}" -eq 1 ]]; then
    TAG_NAME="v${PKG_VERSION}-${PKG_RELEASE}"
    if git -C "${PROJECT_ROOT}" tag -l "${TAG_NAME}" | grep -q .; then
        warn "标签 ${TAG_NAME} 已存在，跳过"
    else
        git -C "${PROJECT_ROOT}" tag -a "${TAG_NAME}" \
            -m "Release ${PKG_VERSION}-${PKG_RELEASE}"
        ok "已创建 git 标签: ${TAG_NAME}"
    fi
fi

# ── 汇总输出 ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=== 归档完成 ===${NC}"
echo "输出目录: ${OUTPUT_DIR}"
echo ""
ls -lh "${OUTPUT_DIR}"
echo ""
echo "RPM 构建命令参考:"
echo "  rpmbuild -ba \\"
echo "    --define '_topdir ~/rpmbuild' \\"
echo "    --define '_sourcedir ${OUTPUT_DIR}' \\"
echo "    ${SPEC_DST}"
