# mcp_server/server.py
import os.path
import sys
import threading
import signal
from functools import wraps
from fastapi import FastAPI
import uvicorn

# 第三方/内部导入
from mcp.server import FastMCP
from config.private.mcp_server.config_loader import McpServerConfig
from servers.oe_cli_mcp_server.mcp_server.manager.manager import ToolManager, logger
from servers.oe_cli_mcp_server.mcp_tools.tool_type import ToolType
from servers.oe_cli_mcp_server.util.get_project_root import get_project_root
from servers.oe_cli_mcp_server.util.zip_tool_util import unzip_tool

# 全局配置
PERSIST_FILE = os.path.join(get_project_root(), "data/tool_state.json")
CONFIG = McpServerConfig().get_config()
FASTAPI_PORT = CONFIG.private_config.fastapi_port

# -------------------------- 简化版线程安全单例装饰器 --------------------------
def singleton(cls):
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
            if _instance:
                _instance.release_resources()  # 重置前释放资源
                _instance = None

    wrapper.reset_instance = reset_instance
    return wrapper

# -------------------------- 核心服务类（简化+内存泄漏修复+协程警告修复） --------------------------
@singleton
class McpServer(ToolManager):
    def __init__(self, name="mcp_server", host="0.0.0.0", port=8080):
        super().__init__()
        # 基础配置
        self.name = name
        self.host = host
        self.port = port
        self.language = CONFIG.public_config.language
        # 核心实例（延迟初始化）
        self.mcp = None
        self.fastapi_app = None
        self.fastapi_thread = None
        self.uvicorn_server = None
        # 注册信号处理（优雅退出）
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    # -------------------------- 资源释放核心方法（统一处理） --------------------------
    def release_resources(self):
        """统一释放所有资源（单例重置/服务退出时调用）"""
        logger.info("开始释放服务资源...")
        # 1. 关闭 FastAPI 服务
        if self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
                logger.info("FastAPI 服务已标记退出")
            except Exception as e:
                logger.error(f"关闭 FastAPI 失败：{str(e)}")
        # 2. 关闭 FastMCP 实例
        if self.mcp and hasattr(self.mcp, "close"):
            try:
                self.mcp.close()
                logger.info("FastMCP 实例已关闭")
            except Exception as e:
                logger.error(f"关闭 FastMCP 失败：{str(e)}")
        # 3. 清理引用（便于 GC 回收）
        self.mcp = None
        self.fastapi_app = None
        self.fastapi_thread = None
        self.uvicorn_server = None
        logger.info("资源释放完成")

    # -------------------------- 信号处理（优雅退出） --------------------------
    def _handle_sigterm(self, signum, frame):
        logger.info(f"收到终止信号（{signum}），准备退出...")
        self.release_resources()
        sys.exit(0)

    # -------------------------- FastAPI 相关（修复协程警告） --------------------------
    def _create_fastapi_app(self):
        """创建 FastAPI 应用（仅保留核心接口）"""
        app = FastAPI(title="MCP Tool API", version="1.0")

        @app.get("/tool/list", summary="查询所有已加载工具包")
        def list_tools():
            try:
                pkg_funcs = {pkg: self.list_funcs(pkg) for pkg in self.list_packages()}
                return {"success": True, "data": {"pkg_funcs": pkg_funcs, "total_packages": len(pkg_funcs)}}
            except Exception as e:
                logger.error(f"查询工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": str(e)}

        @app.post("/tool/add", summary="添加工具包（system/custom）")
        def add_tool(type: str, value: str):
            try:
                if type == "system":
                    self.load(ToolType(value))
                else:
                    self.load(value)
                return {"success": True, "message": f"添加 {value} 成功"}
            except Exception as e:
                logger.error(f"添加工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": str(e)}

        @app.post("/tool/remove", summary="删除工具包（system/custom）")
        def remove_tool(type: str, value: str):
            try:
                target = ToolType(value) if type == "system" else value
                self.remove(target)
                return {"success": True, "message": f"删除 {value} 成功（重启后生效）"}
            except Exception as e:
                logger.error(f"删除工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": str(e)}

        @app.post("/tool/init", summary="初始化工具包（仅保留基础包）")
        def init_tool():
            try:
                self.init()
                return {"success": True, "message": "初始化成功（仅保留基础运维包，重启后生效）"}
            except Exception as e:
                logger.error(f"初始化失败：{str(e)}", exc_info=True)
                return {"success": False, "message": str(e)}

        return app

    def _start_fastapi(self):
        """启动 FastAPI 服务（修复协程未 await 警告）"""
        self.fastapi_app = self._create_fastapi_app()

        def run_server():
            try:
                config = uvicorn.Config(
                    self.fastapi_app,
                    host="0.0.0.0",
                    port=FASTAPI_PORT,
                    log_level="warning",
                    access_log=False
                )
                self.uvicorn_server = uvicorn.Server(config)
                # 修复：用 run() 替代 serve()，run() 是同步方法，内部处理 await
                self.uvicorn_server.run()
            except Exception as e:
                logger.error(f"FastAPI 启动失败：{str(e)}", exc_info=True)

        # 避免重复启动
        if self.fastapi_thread and self.fastapi_thread.is_alive():
            return
        self.fastapi_thread = threading.Thread(target=run_server, daemon=True)
        self.fastapi_thread.start()
        logger.info(f"FastAPI 服务启动：http://0.0.0.0:{FASTAPI_PORT}/docs")

    # -------------------------- 核心业务方法（简化+修复） --------------------------
    def _reset(self):
        """重置 MCP 实例（修复资源释放）"""
        logger.info("重置 MCP 实例...")
        # 释放旧实例资源
        if self.mcp and hasattr(self.mcp, "close"):
            self.mcp.close()
        # 重新创建 MCP 实例
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        # 恢复工具状态
        self.restore_tool_state()
        self.reload_package_functions()
        for pkg in self.list_packages():
            self.load(pkg)
        logger.info("MCP 实例重置完成")

    def load(self, mcp_collection: ToolType | str):
        """加载工具包（保留原有逻辑，简化日志）"""
        before_count = len(self.list_packages())
        try:
            if isinstance(mcp_collection, str):
                # 处理自定义 zip 包
                if mcp_collection.endswith(".zip"):
                    unzip_tool(mcp_collection)
                    pkg_name = os.path.basename(mcp_collection)[:-4]
                    pkg_dir = os.path.join(get_project_root(), "mcp_tools/personal_tools", pkg_name)
                else:
                    pkg_name = mcp_collection
                    pkg_dir = self.get_package_path(pkg_name)
                if pkg_dir in self.list_packages():
                    logger.warning(f"{pkg_name} 已加载，跳过")
                    return
                self.load_package(pkg_dir)
                packages_to_register = [pkg_name]
            elif isinstance(mcp_collection, ToolType):
                tool_type = mcp_collection.value
                if tool_type in self.list_tool_types():
                    logger.warning(f"{tool_type} 已加载，跳过")
                    return
                load_result = self.load_tool_type(tool_type)
                if load_result["success_package"] == 0:
                    logger.error(f"{tool_type} 加载失败：{load_result['fail_reason']}")
                    return
                packages_to_register = [pkg for pkg in self.list_packages(tool_type) if pkg not in self.list_packages()[:before_count]]
            else:
                logger.error(f"不支持的加载类型：{type(mcp_collection)}")
                return
            # 注册工具
            for pkg in packages_to_register:
                for func_name in self.list_funcs(pkg):
                    func_info = self.get_func_info(func_name)
                    desc = func_info["description"]["zh"] if self.language == "zh" else func_info["description"]["en"]
                    self.mcp.tool(name=func_name, description=desc)(func_info["func"])
            logger.info(f"加载成功：新增 {len(packages_to_register)} 个包，当前共 {len(self.list_packages())} 个")
        except Exception as e:
            logger.error(f"加载 {mcp_collection} 失败：{str(e)}", exc_info=True)

    def remove(self, mcp_collection):
        """卸载工具包（修复模块引用清理）"""
        try:
            # 原有卸载逻辑
            if isinstance(mcp_collection, ToolType):
                self.unload_tool_type(mcp_collection.value)
            else:
                self.unload_package(mcp_collection)
            # 清理 sys.modules 中的模块引用（关键）
            pkg_name = mcp_collection.value if isinstance(mcp_collection, ToolType) else mcp_collection
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith(f"{pkg_name}.") or mod_name == pkg_name:
                    del sys.modules[mod_name]
            self._reset()
        except Exception as e:
            logger.error(f"卸载 {mcp_collection} 失败：{str(e)}", exc_info=True)

    def init(self):
        """初始化工具包（仅保留基础包）"""
        for tool_type in self.list_tool_types():
            self.unload_tool_type(tool_type)
        self.release_resources()
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        self.load(ToolType.BASE)
        logger.info("初始化完成：仅保留基础运维包（重启后生效）")

    def restart(self):
        """重启服务"""
        self._reset()
        self.start()

    # -------------------------- 服务启动入口（简化） --------------------------
    def start(self):
        """启动核心服务（FastAPI + FastMCP）"""
        logger.info("启动 MCP 服务...")
        # 1. 初始化 MCP
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        self.restore_tool_state()
        self.reload_package_functions()
        # 加载已存在的包，无包则加载基础包
        packages = self.list_packages()
        if packages:
            for pkg in packages:
                self.load(pkg)
        else:
            self.load(ToolType.BASE)
        # 2. 启动 FastAPI
        self._start_fastapi()
        # 3. 启动 FastMCP（阻塞主线程）
        logger.info(f"FastMCP 服务启动：{self.host}:{self.port}（持久化文件：{PERSIST_FILE}）")
        self.mcp.run(transport='sse')

# -------------------------- 启动入口 --------------------------
if __name__ == "__main__":
    # 初始化并启动服务
    mcp_server = McpServer()
    mcp_server.start()