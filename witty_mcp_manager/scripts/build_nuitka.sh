#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2024-2026 openEuler SIG-Intelligence
#
# Nuitka build script for witty-mcp binary
#
# Prerequisites:
#   - Python 3.11+
#   - GCC / Clang
#   - patchelf (for Linux)
#   - ccache (optional, speeds up rebuild)
#   - pip install nuitka ordered-set
#
# Usage:
#   ./scripts/build_nuitka.sh [--mode onefile|standalone] [--output-dir DIR]
#
# Examples:
#   ./scripts/build_nuitka.sh                      # default: onefile mode
#   ./scripts/build_nuitka.sh --mode standalone    # standalone directory mode
#   ./scripts/build_nuitka.sh --output-dir /opt    # custom output directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${PROJECT_ROOT}/src"
ENTRY_POINT="${SRC_DIR}/witty_mcp_manager/__main__.py"

# Default options
MODE="onefile"
OUTPUT_DIR="${PROJECT_ROOT}/dist"
CLEAN_BUILD=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --clean)
            CLEAN_BUILD=1
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --mode MODE        Build mode: onefile (default) or standalone"
            echo "  --output-dir DIR   Output directory (default: ./dist)"
            echo "  --clean            Clean build directories before building"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Validate mode
if [[ "$MODE" != "onefile" && "$MODE" != "standalone" ]]; then
    echo "Error: Invalid mode '$MODE'. Use 'onefile' or 'standalone'." >&2
    exit 1
fi

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required" >&2; exit 1; }
command -v gcc >/dev/null 2>&1 || command -v clang >/dev/null 2>&1 || { echo "Error: C compiler (gcc/clang) is required" >&2; exit 1; }

# Check Nuitka
if ! python3 -c "import nuitka" 2>/dev/null; then
    echo "Error: Nuitka is not installed. Run: pip install nuitka ordered-set" >&2
    exit 1
fi

# Check patchelf on Linux
if [[ "$(uname -s)" == "Linux" ]]; then
    command -v patchelf >/dev/null 2>&1 || { echo "Error: patchelf is required on Linux" >&2; exit 1; }
fi

echo "=============================================="
echo "Witty MCP Manager - Nuitka Build"
echo "=============================================="
echo "Mode:        ${MODE}"
echo "Output:      ${OUTPUT_DIR}"
echo "Entry:       ${ENTRY_POINT}"
echo "Python:      $(python3 --version)"
echo "Nuitka:      $(python3 -m nuitka --version | head -1)"
echo "=============================================="

# Clean if requested
if [[ "$CLEAN_BUILD" -eq 1 ]]; then
    echo "[1/4] Cleaning previous build artifacts..."
    rm -rf "${OUTPUT_DIR}"/__main__.build \
           "${OUTPUT_DIR}"/__main__.dist \
           "${OUTPUT_DIR}"/__main__.onefile-build \
           "${OUTPUT_DIR}"/witty-mcp
else
    echo "[1/4] Skipping clean (use --clean to force)"
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Install dependencies to virtual environment if not already
echo "[2/4] Ensuring dependencies are available..."
cd "${PROJECT_ROOT}"
if [[ -f "uv.lock" ]] && command -v uv >/dev/null 2>&1; then
    uv sync --quiet 2>/dev/null || true
fi

# Build with Nuitka
echo "[3/4] Building with Nuitka (mode=${MODE})..."

# Common optimization flags
NUITKA_OPTS=(
    "--mode=${MODE}"
    "--output-dir=${OUTPUT_DIR}"
    "--output-filename=witty-mcp"
    
    # Include our package
    "--include-package=witty_mcp_manager"
    
    # Include template files for CLI renderer
    "--include-data-dir=${SRC_DIR}/witty_mcp_manager/cli/templates=witty_mcp_manager/cli/templates"
    
    # Anti-bloat optimizations (reduce size) - plugin is auto-enabled
    "--noinclude-pytest-mode=nofollow"
    "--noinclude-setuptools-mode=nofollow"
    "--noinclude-custom-mode=setuptools:nofollow"
    "--noinclude-custom-mode=pip:nofollow"
    "--noinclude-custom-mode=wheel:nofollow"
    "--noinclude-custom-mode=distutils:nofollow"
    "--noinclude-custom-mode=pkg_resources:nofollow"
    
    # Remove debug/test code
    "--python-flag=no_docstrings"
    "--python-flag=-OO"
    
    # Remove assertion checks in release
    "--python-flag=no_asserts"
    
    # Disable some warnings we don't care about
    "--nowarn-mnemonic=not-given-as-argument"
)

# Note: Nuitka auto-detects ccache via CC environment or system path
# No explicit flag needed - ccache is used automatically if installed

# Add static libpython if building standalone/onefile (Linux only)
if [[ "$(uname -s)" == "Linux" ]]; then
    # Use system libpython if static is not available
    NUITKA_OPTS+=("--static-libpython=auto")
fi

# Execute Nuitka
PYTHONPATH="${SRC_DIR}:${PYTHONPATH:-}" python3 -m nuitka "${NUITKA_OPTS[@]}" "${ENTRY_POINT}"

# Verify output
echo "[4/4] Verifying build..."
if [[ "${MODE}" == "standalone" ]]; then
    BINARY="${OUTPUT_DIR}/__main__.dist/witty-mcp"
else
    BINARY="${OUTPUT_DIR}/witty-mcp"
fi

if [[ ! -f "$BINARY" ]]; then
    echo "Error: Build failed - binary not found at ${BINARY}" >&2
    exit 1
fi

# Get file info
SIZE=$(du -h "${BINARY}" | cut -f1)
FILE_TYPE=$(file "${BINARY}" | cut -d: -f2)

echo ""
echo "=============================================="
echo "Build successful!"
echo "=============================================="
echo "Binary:      ${BINARY}"
echo "Size:        ${SIZE}"
echo "Type:        ${FILE_TYPE}"
echo ""
echo "Test with:"
echo "  ${BINARY} version"
echo "  ${BINARY} --help"
echo "=============================================="
