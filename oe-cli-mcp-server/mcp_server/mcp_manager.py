# mcp_server/server.py
import json
import os.path
import threading
from functools import wraps
from typing import Dict, Any, Optional
from mcp.server import FastMCP
from config.base_config_loader import BaseConfig
from mcp_server.manager.manager import ToolManager, logger
from mcp_tools.tool_type import ToolType
from util.get_project_root import get_project_root
from util.zip_tool_util import unzip_tool

# -------------------------- 导入独立的 FastAPI 启动函数 --------------------------
from mcp_server.api_server import start_fastapi_server

PUBLIC_CONFIG_PATH = os.path.join(get_project_root(), "config/public_config.toml")
PERSIST_FILE = os.path.join(get_project_root(), "data/tool_state.json")

def singleton(cls):
    """线程安全的单例装饰器，不侵入原有类逻辑"""
    _instance = None
    _lock = threading.Lock()

    @wraps(cls)
    def wrapper(*args, **kwargs):
        nonlocal _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls(*args, **kwargs)
        return _instance

    def reset_instance():
        nonlocal _instance
        with _lock:
            _instance = None

    wrapper.reset_instance = reset_instance
    wrapper._instance = _instance  # 暴露 _instance 属性，供 API 服务调用
    return wrapper

@singleton
class McpServer(ToolManager):
    def __init__(self, name, host, port):
        super().__init__()
        self.mcp = FastMCP(name, host=host, port=port)
        self.host = host
        self.port = port
        self.language = BaseConfig().get_config().public_config.language
        self.PERSIST_FILE = PERSIST_FILE

    # -------------------------- 原有核心业务方法不变 --------------------------
    def _mcp_register(self, packages=None):
        if not packages:
            packages = self.list_packages()
        for package_name in packages:
            func_names = self.list_funcs(package_name)
            for func_name in func_names:
                func_info = self.get_func_info(func_name)
                tool_func = func_info["func"]
                description = func_info["description"]["zh"] if self.language == "zh" else func_info["description"]["en"]
                self.mcp.tool(name=func_name, description=description)(tool_func)
        logger.info("tool 注册成功")
        return self.mcp

    def _reset(self):
        del self.mcp
        self.mcp = FastMCP("mcp实例", host=self.host, port=self.port)
        self.restore_tool_state()
        self.reload_package_functions()
        for pkg in self.list_packages():
            self.load(pkg)

    def load(self, mcp_collection: ToolType | str):
        before_pkg_count = len(self.list_packages())
        if isinstance(mcp_collection, str):
            if os.path.basename(mcp_collection)[:-4] == ".zip":
                unzip_tool(mcp_collection)
                package_name = os.path.basename(mcp_collection)[:-4]
                package_dir = os.path.join(get_project_root(), "mcp_tools/personal_tools", package_name)
            else:
                package_name = mcp_collection
                package_dir = self.get_package_path(package_name)
            if package_dir in self.list_packages():
                logger.warning(f"自定义包 {package_name} 已加载，无需重复添加")
                return
            result = self.load_package(package_dir)
            if not result:
                logger.error(f"自定义包 {package_name} 加载失败")
                return
            packages_to_register = [package_name]
        elif isinstance(mcp_collection, ToolType):
            tool_type_value = mcp_collection.value
            if tool_type_value in self.list_tool_types():
                logger.warning(f"系统包类型 {tool_type_value} 已加载，无需重复添加")
                return
            load_result = self.load_tool_type(tool_type_value)
            if load_result["success_package"] == 0:
                logger.error(f"系统包类型 {tool_type_value} 加载失败：{load_result['fail_reason']}")
                return
            packages_to_register = [pkg for pkg in self.list_packages(tool_type_value)
                                    if pkg not in self.list_packages()[:before_pkg_count]]
        else:
            logger.error(f"不支持的加载类型：{type(mcp_collection)}")
            return
        self._mcp_register(packages_to_register)
        after_pkg_count = len(self.list_packages())
        logger.info(f"加载成功：原有 {before_pkg_count} 个包，新增 {after_pkg_count - before_pkg_count} 个包，当前共 {after_pkg_count} 个包")

    def remove(self, mcp_collection):
        if isinstance(mcp_collection, ToolType):
            self.unload_tool_type(mcp_collection.value)
        else:
            self.unload_package(mcp_collection)
        self._reset()

    def init(self):
        del self.mcp
        all_types = self.list_tool_types()
        for mcp_type in all_types:
            self.unload_tool_type(mcp_type)
        BaseConfig().update_config(default=True)
        self.reload_config()
        self.mcp = FastMCP("mcp实例", host=self.host, port=self.port)
        self.load(ToolType.BASE)
        logger.info(f"初始化完成：仅保留基础运维包")

    def reload_config(self):
        import toml
        BaseConfig().update_config()
        with open(PUBLIC_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = toml.load(f)
        self.port = config["port"]
        self.host = config["host"]

    def restart(self):
        self._reset()
        self.start()

    # -------------------------- 简化 start 方法：调用独立的 FastAPI 启动函数 --------------------------
    def start(self):
        # 1. 启动独立的 FastAPI 服务（线程不阻塞）
        start_fastapi_server(host="0.0.0.0", port=8003)
        # 2. 启动 FastMCP 主服务（原有逻辑不变）
        self._reset()
        self.mcp.run(transport='sse')

# -------------------------- 启动服务（原有逻辑不变）--------------------------
if __name__ == "__main__":
    config = BaseConfig().get_config().public_config
    mcp_server = McpServer("MCP_Tool_Service", config.host, config.port)
    mcp_server.start()