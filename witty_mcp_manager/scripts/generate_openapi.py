#!/usr/bin/env python3
"""
生成 Witty MCP Manager 的 OpenAPI 文档

使用方式:
    cd witty_mcp_manager
    uv run python scripts/generate_openapi.py
    uv run python scripts/generate_openapi.py --format yaml
    uv run python scripts/generate_openapi.py --output docs/api.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def generate_openapi_spec() -> dict:
    """生成 OpenAPI 规范"""
    from witty_mcp_manager.ipc.server import create_app_for_docs  # noqa: PLC0415

    # 创建仅用于文档生成的 app
    app = create_app_for_docs()
    return app.openapi()


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description="生成 Witty MCP Manager OpenAPI 文档")
    parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="输出格式 (默认: json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="输出文件路径 (默认: stdout)",
    )
    args = parser.parse_args()

    # 生成规范
    spec = generate_openapi_spec()

    # 格式化输出
    if args.format == "json":
        content = json.dumps(spec, indent=2, ensure_ascii=False)
    else:  # yaml
        try:
            import yaml  # noqa: PLC0415

            content = yaml.dump(spec, allow_unicode=True, sort_keys=False)
        except ImportError:
            print("错误: YAML 格式需要安装 PyYAML: pip install pyyaml", file=sys.stderr)  # noqa: T201
            sys.exit(1)

    # 输出
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"OpenAPI 文档已生成: {args.output}")  # noqa: T201
    else:
        print(content)  # noqa: T201


if __name__ == "__main__":
    main()
