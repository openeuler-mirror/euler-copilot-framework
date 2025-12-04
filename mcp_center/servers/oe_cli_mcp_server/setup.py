from setuptools import setup, find_packages

setup(
    name="mcp-server",  # 命令名
    version="0.1.0",
    packages=find_packages(),  # 自动找到 mcp_server 模块
    entry_points={
        "console_scripts": [
            # 配置命令：mcp-server → 指向 cli.py 的 main 函数
            "mcp-server = mcp_server.cli.cli:main",
        ],
    },
    python_requires=">=3.9",  # 你的 Python 版本要求
)