# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 安装"""

from asyncio import subprocess
from typing import TYPE_CHECKING
import logging
import os
import shutil
from apps.constants import MCP_PATH

if TYPE_CHECKING:
    from apps.schemas.mcp import MCPServerStdioConfig

logger = logging.getLogger(__name__)


async def install_uvx(mcp_id: str, config: "MCPServerStdioConfig") -> "MCPServerStdioConfig | None":
    """
    安装使用uvx包管理器的MCP服务

    安装在 ``template`` 目录下，会作为可拷贝的MCP模板；
    这个函数运行在子进程中，因此直接使用print输出日志

    :param str mcp_id: MCP模板ID
    :param MCPServerStdioConfig config: MCP配置
    :return: MCP配置
    :rtype: MCPServerStdioConfig
    :raises ValueError: 未找到MCP Server对应的Python包
    """
    uv_path = shutil.which('uv')
    if uv_path is None:
        error = "[Installer] 未找到uv命令，请先安装uv包管理器: pip install uv"
        logging.error(error)
        raise Exception(error)
    # 找到包名
    package = None
    for arg in config.args:
        if not arg.startswith("-"):
            package = arg
            break
    logger.error(f"[Installer] MCP包名: {package}")
    if not package:
        print("[Installer] 未找到包名")  # noqa: T201
        return None
    # 创建文件夹
    mcp_path = MCP_PATH / "template" / mcp_id / "project"
    logger.error(f"[Installer] MCP安装路径: {mcp_path}")
    await mcp_path.mkdir(parents=True, exist_ok=True)
    # 如果有pyproject.toml文件，则使用sync
    flag = await (mcp_path / "pyproject.toml").exists()
    logger.error(f"[Installer] MCP安装标志: {flag}")
    if await (mcp_path / "pyproject.toml").exists():
        shell_command = f"{uv_path} venv; {uv_path} sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --active --no-install-project --no-cache"
        logger.error(f"[Installer] MCP安装命令: {shell_command}")
        pipe = await subprocess.create_subprocess_shell(
            (
                f"{uv_path} venv; "
                f"{uv_path} sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --active "
                "--no-install-project --no-cache"
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=mcp_path,
            env={"PYTHONPATH": str(mcp_path), "VIRTUAL_ENV": str(mcp_path / ".venv")},
        )
        stdout, stderr = await pipe.communicate()
        if pipe.returncode != 0:
            print(f"[Installer] 检查依赖失败: {stderr.decode() if stderr else '（无报错信息）'}")  # noqa: T201
            return None
        print(f"[Installer] 检查依赖成功: {mcp_path}; {stdout.decode() if stdout else '（无输出信息）'}")  # noqa: T201

        config.command = uv_path
        if "run" not in config.args:
            config.args = ["run", *config.args]
        config.auto_install = False
        logger.error(f"[Installer] MCP安装配置更新成功: {config}")
        return config

    # 否则，初始化uv项目
    pipe = await subprocess.create_subprocess_shell(
        (
            f"{uv_path} init; "
            f"{uv_path} venv; "
            f"{uv_path} add --index-url https://pypi.tuna.tsinghua.edu.cn/simple {package}; "
            f"{uv_path} sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --active "
            f"--no-install-project --no-cache"
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=mcp_path,
        env={"PYTHONPATH": str(mcp_path), "VIRTUAL_ENV": str(mcp_path / ".venv")},
    )
    stdout, stderr = await pipe.communicate()
    if pipe.returncode != 0:
        print(f"[Installer] 安装 {package} 失败: {stderr.decode() if stderr else '（无报错信息）'}")  # noqa: T201
        return None
    print(f"[Installer] 安装 {package} 成功: {mcp_path}; {stdout.decode() if stdout else '（无输出信息）'}")  # noqa: T201

    # 更新配置
    config.command = uv_path
    if "run" not in config.args:
        config.args = ["run", *config.args]
    config.auto_install = False

    return config


async def install_npx(mcp_id: str, config: "MCPServerStdioConfig") -> "MCPServerStdioConfig | None":
    """
    安装使用npx包管理器的MCP服务

    安装在 ``template`` 目录下，会作为可拷贝的MCP模板

    :param str mcp_id: MCP模板ID
    :param MCPServerStdioConfig config: MCP配置
    :return: MCP配置
    :rtype: MCPServerStdioConfig
    :raises ValueError: 未找到MCP Server对应的npm包
    """
    npm_path = shutil.which('npm')
    if npm_path is None:
        error = "[Installer] 未找到npm命令，请先安装Node.js和npm"
        logging.error(error)
        raise Exception(error)
    # 查找package name
    package = None
    for arg in config.args:
        if not arg.startswith("-"):
            package = arg
            break

    if not package:
        print("[Installer] 未找到包名")  # noqa: T201
        return None
    mcp_path = MCP_PATH / "template" / mcp_id / "project"
    await mcp_path.mkdir(parents=True, exist_ok=True)
    # 如果有node_modules文件夹，则认为已安装
    if await (mcp_path / "node_modules").exists():
        config.command = npm_path
        if "exec" not in config.args:
            config.args = ["exec", *config.args]
        return config

    # 安装NPM包
    pipe = await subprocess.create_subprocess_shell(
        f"{npm_path} install {package}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=mcp_path,
    )
    stdout, stderr = await pipe.communicate()
    if pipe.returncode != 0:
        print(f"[Installer] 安装 {package} 失败: {stderr.decode() if stderr else '（无报错信息）'}")  # noqa: T201
        return None
    print(f"[Installer] 安装 {package} 成功: {mcp_path}; {stdout.decode() if stdout else '（无输出信息）'}")  # noqa: T201

    # 更新配置
    config.command = npm_path
    if "exec" not in config.args:
        config.args = ["exec", *config.args]
    config.auto_install = False

    return config
