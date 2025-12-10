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
FASTAPI_PORT = CONFIG.private_config.fastapi_port  # 确保配置中是 12556
FASTMCP_PORT = CONFIG.private_config.port  # 确保配置中是 12555（区分FastMCP端口）

# -------------------------- 线程安全单例装饰器（保留） --------------------------
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

# -------------------------- 核心服务类（关键修复） --------------------------
@singleton
class McpServer(ToolManager):
    def __init__(self, name="mcp_server", host="0.0.0.0", port=FASTMCP_PORT):
        super().__init__()
        # 基础配置
        self.name = name
        self.host = host
        self.port = port  # FastMCP 端口（12555）
        self.language = CONFIG.public_config.language
        # 核心实例（延迟初始化）
        self.mcp = None
        self.fastapi_app = None
        self.fastapi_thread = None
        self.uvicorn_server = None
        self._fastapi_started = False  # 防止FastAPI重复启动的标记
        # 注册信号处理（优雅退出）
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    # -------------------------- 资源释放核心方法（优化） --------------------------
    def release_resources(self):
        """统一释放所有资源（单例重置/服务退出时调用）"""
        logger.info("开始释放服务资源...")
        # 1. 关闭 FastAPI 服务（优化关闭逻辑）
        if self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
                # 等待FastAPI线程退出（最多等3秒）
                if self.fastapi_thread and self.fastapi_thread.is_alive():
                    self.fastapi_thread.join(timeout=3)
                logger.info("FastAPI 服务已关闭")
            except Exception as e:
                logger.error(f"关闭 FastAPI 失败：{str(e)}")
        # 2. 关闭 FastMCP 实例（兼容不同版本）
        if self.mcp:
            try:
                if hasattr(self.mcp, "close"):
                    self.mcp.close()
                elif hasattr(self.mcp, "stop"):
                    self.mcp.stop()
                logger.info("FastMCP 实例已关闭")
            except Exception as e:
                logger.error(f"关闭 FastMCP 失败：{str(e)}")
        # 3. 清理引用（便于GC回收）
        self.mcp = None
        self.fastapi_app = None
        self.fastapi_thread = None
        self.uvicorn_server = None
        self._fastapi_started = False  # 重置启动标记
        logger.info("资源释放完成")

    # -------------------------- 信号处理（保留） --------------------------
    def _handle_sigterm(self, signum, frame):
        logger.info(f"收到终止信号（{signum}），准备退出...")
        self.release_resources()
        sys.exit(0)

    # -------------------------- FastAPI 相关（修复重复启动） --------------------------
    def _create_fastapi_app(self):
        """创建 FastAPI 应用（保留核心接口，优化返回信息）"""
        app = FastAPI(title="MCP Tool API", version="1.0")

        @app.get("/tool/list", summary="查询所有已加载工具包")
        def list_tools():
            try:
                pkg_funcs = {pkg: self.list_funcs(pkg) for pkg in self.list_packages()}
                return {
                    "success": True,
                    "data": {"pkg_funcs": pkg_funcs, "total_packages": len(pkg_funcs)},
                    "message": "查询成功"
                }
            except Exception as e:
                logger.error(f"查询工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"查询失败：{str(e)}"}

        @app.post("/tool/add", summary="添加工具包（system/custom）")
        def add_tool(type: str, value: str):
            try:
                if type not in ["system", "custom"]:
                    return {"success": False, "message": "type必须是system或custom"}
                if type == "system":
                    self.load(ToolType(value))
                else:
                    self.load(value)
                return {"success": True, "message": f"添加 {value} 成功（实时生效）"}
            except Exception as e:
                logger.error(f"添加工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"添加失败：{str(e)}"}

        @app.post("/tool/remove", summary="删除工具包（system/custom）")
        def remove_tool(type: str, value: str):
            try:
                if type not in ["system", "custom"]:
                    return {"success": False, "message": "type必须是system或custom"}
                target = ToolType(value) if type == "system" else value
                self.remove(target)
                return {"success": True, "message": f"删除 {value} 成功（实时生效）"}
            except Exception as e:
                logger.error(f"删除工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"删除失败：{str(e)}"}

        @app.post("/tool/init", summary="初始化工具包（仅保留基础包）")
        def init_tool():
            try:
                self.init()
                return {"success": True, "message": "初始化成功（仅保留基础运维包，实时生效）"}
            except Exception as e:
                logger.error(f"初始化失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"初始化失败：{str(e)}"}

        return app

    def _start_fastapi(self):
        """启动 FastAPI 服务（修复重复启动+协程警告）"""
        # 防止重复启动（核心修复）
        if self._fastapi_started or (self.fastapi_thread and self.fastapi_thread.is_alive()):
            logger.warning("FastAPI 服务已启动，无需重复启动")
            return

        self.fastapi_app = self._create_fastapi_app()

        def run_server():
            try:
                config = uvicorn.Config(
                    self.fastapi_app,
                    host="0.0.0.0",
                    port=FASTAPI_PORT,  # 固定FastAPI端口（12556）
                    log_level="warning",
                    access_log=False,
                    reload=False  # 禁用热重载（避免重复进程）
                )
                self.uvicorn_server = uvicorn.Server(config)
                self.uvicorn_server.run()  # 同步运行，修复协程警告
            except Exception as e:
                logger.error(f"FastAPI 启动失败：{str(e)}", exc_info=True)
            finally:
                self._fastapi_started = False  # 线程退出后重置标记

        self.fastapi_thread = threading.Thread(target=run_server, daemon=True)
        self.fastapi_thread.start()
        self._fastapi_started = True  # 标记已启动
        logger.info(f"FastAPI 服务启动：http://0.0.0.0:{FASTAPI_PORT}/docs")

    # -------------------------- 核心业务方法（关键修复） --------------------------
    def _reset(self):
        """重置 MCP 实例（修复重复加载+资源泄漏）"""
        logger.info("重置 MCP 实例...")
        # 1. 释放旧实例资源
        if self.mcp:
            try:
                if hasattr(self.mcp, "close"):
                    self.mcp.close()
            except Exception as e:
                logger.error(f"关闭旧 FastMCP 实例失败：{str(e)}")
        # 2. 重新创建 FastMCP 实例（确保干净）
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        # 3. 恢复工具状态+重新加载函数（无需重复load包！）
        self.restore_tool_state()
        self.reload_package_functions()  # 已包含包的加载逻辑
        # 4. 重新注册所有工具（仅注册一次）
        self._register_all_tools()
        logger.info(f"MCP 实例重置完成，当前加载 {len(self.list_packages())} 个包")

    def _register_all_tools(self):
        """统一注册所有工具（去掉工具已注册判断，直接注册/覆盖）"""
        for pkg in self.list_packages():
            for func_name in self.list_funcs(pkg):
                func_info = self.get_func_info(func_name)
                desc = func_info["description"]["zh"] if self.language == "zh" else func_info["description"]["en"]
                # 直接注册：FastMCP 重复注册同一名称工具会自动覆盖，无需判断
                self.mcp.tool(name=func_name, description=desc)(func_info["func"])
        logger.info(f"工具注册完成：共注册 {sum(len(self.list_funcs(pkg)) for pkg in self.list_packages())} 个函数")

    def load(self, mcp_collection: ToolType | str):
        """加载工具包（修复重复加载+实时注册）"""
        before_count = len(self.list_packages())
        try:
            packages_to_register = []
            if isinstance(mcp_collection, str):
                # 处理自定义 zip 包
                if mcp_collection.endswith(".zip"):
                    unzip_tool(mcp_collection)
                    pkg_name = os.path.basename(mcp_collection)[:-4]
                    pkg_dir = os.path.join(get_project_root(), "mcp_tools/personal_tools", pkg_name)
                else:
                    pkg_name = mcp_collection
                    pkg_dir = self.get_package_path(pkg_name)
                # 双重去重（避免重复加载）
                if not pkg_dir or pkg_name in self.list_packages():
                    logger.warning(f"包 {pkg_name} 已加载或路径无效，跳过")
                    return
                # 加载包（ToolManager的核心方法）
                if not self.load_package(pkg_dir):
                    logger.error(f"加载包目录 {pkg_dir} 失败")
                    return
                packages_to_register = [pkg_name]
            elif isinstance(mcp_collection, ToolType):
                tool_type = mcp_collection.value
                # 去重：避免重复加载同类型系统包
                if tool_type in self.list_tool_types():
                    logger.warning(f"系统包类型 {tool_type} 已加载，跳过")
                    return
                # 加载系统包类型
                load_result = self.load_tool_type(tool_type)
                if load_result["success_package"] == 0:
                    logger.error(f"系统包类型 {tool_type} 加载失败：{load_result['fail_reason']}")
                    return
                # 筛选新增的包（避免重复注册）
                packages_to_register = [
                    pkg for pkg in self.list_packages(tool_type)
                    if pkg not in self.list_packages()[:before_count]
                ]
            else:
                logger.error(f"不支持的加载类型：{type(mcp_collection)}")
                return

            # 实时注册新增工具（无需等_reset）
            if packages_to_register:
                self._register_all_tools()  # 注册所有工具（确保不遗漏）
                logger.info(f"加载成功：新增 {len(packages_to_register)} 个包，当前共 {len(self.list_packages())} 个（实时生效）")
        except Exception as e:
            logger.error(f"加载 {mcp_collection} 失败：{str(e)}", exc_info=True)

    def remove(self, mcp_collection):
        """卸载工具包（修复内存泄漏+实时生效）"""
        try:
            pkg_names = []
            # 1. 卸载工具包（更新ToolManager状态）
            if isinstance(mcp_collection, ToolType):
                tool_type = mcp_collection.value
                pkg_names = self.list_packages(tool_type)  # 获取该类型下所有包
                self.unload_tool_type(tool_type)
            else:
                pkg_name = mcp_collection
                pkg_names = [pkg_name]
                self.unload_package(pkg_name)

            # 2. 清理模块缓存（修复内存泄漏）
            for pkg_name in pkg_names:
                for mod_name in list(sys.modules.keys()):
                    if mod_name.startswith(f"{pkg_name}.") or mod_name == pkg_name:
                        del sys.modules[mod_name]
                        logger.debug(f"清理模块缓存：{mod_name}")

            # 3. 实时重置MCP（更新注册状态，无需重启）
            self._reset()
            logger.info(f"删除成功：已卸载 {len(pkg_names)} 个包（实时生效）")
        except Exception as e:
            logger.error(f"卸载 {mcp_collection} 失败：{str(e)}", exc_info=True)

    def init(self):
        """初始化工具包（修复实时生效+重复加载）"""
        logger.info("开始初始化工具包...")
        # 1. 卸载所有工具类型
        all_types = self.list_tool_types()
        for tool_type in all_types:
            self.unload_tool_type(tool_type)
        # 2. 清理模块缓存（彻底释放内存）
        base_tools_dir = "/home/tsn/framework-dev-with-mcp/mcp_center/servers/oe_cli_mcp_server/mcp_tools/base_tools"
        # 确保目录存在
        if os.path.exists(base_tools_dir):
            # 读取目录下的所有子目录（排除文件和隐藏目录）
            module_prefixes = [
                dir_name for dir_name in os.listdir(base_tools_dir)
                if os.path.isdir(os.path.join(base_tools_dir, dir_name))
                   and not dir_name.startswith(".")  # 排除隐藏目录（如 .git）
            ]

            # 2. 清理这些模块的缓存（动态前缀）
            for mod_name in list(sys.modules.keys()):
                # 判断模块名是否以任一基础工具目录名为前缀（或完全匹配）
                if any(
                        mod_name == prefix or mod_name.startswith(f"{prefix}.")
                        for prefix in module_prefixes
                ):
                    del sys.modules[mod_name]
                    logger.debug(f"清理模块缓存：{mod_name}")
        else:
            logger.warning(f"base_tools 目录不存在：{base_tools_dir}，跳过模块缓存清理")
        # 3. 重置配置（保留基础包配置）
        self.reload_config()  # 确保加载最新配置
        # 4. 重置MCP实例（干净状态）
        self.release_resources()
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        # 5. 加载基础包（实时注册）
        self.load(ToolType.BASE)
        logger.info("初始化完成：仅保留基础运维包（实时生效）")

    def reload_config(self):
        """重新加载配置（补充实现，确保配置生效）"""
        global CONFIG
        CONFIG = McpServerConfig().get_config()
        self.language = CONFIG.public_config.language
        self.host = CONFIG.private_config.host
        self.port = CONFIG.private_config.port

    def restart(self):
        """重启服务（优化流程）"""
        logger.info("重启 MCP 服务...")
        self.release_resources()
        self.start()

    # -------------------------- 服务启动入口（优化） --------------------------
    def start(self):
        """启动核心服务（FastAPI + FastMCP，避免重复加载）"""
        logger.info("启动 MCP 服务...")
        # 1. 初始化MCP实例（确保干净）
        if not self.mcp:
            self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        # 2. 恢复工具状态+加载函数（避免重复load）
        self.restore_tool_state()
        self.reload_package_functions()
        # 3. 加载基础包（无包时）
        if not self.list_packages():
            self.load(ToolType.BASE)
        # 4. 注册所有工具（仅一次）
        self._register_all_tools()
        # 5. 启动FastAPI（防止重复）
        self._start_fastapi()
        # 6. 启动FastMCP（阻塞主线程）
        logger.info(f"FastMCP 服务启动：{self.host}:{self.port}（持久化文件：{PERSIST_FILE}）")
        try:
            self.mcp.run(transport='sse')
        except Exception as e:
            logger.error(f"FastMCP 服务运行失败：{str(e)}", exc_info=True)
            self.release_resources()
            sys.exit(1)

# -------------------------- 启动入口 --------------------------
if __name__ == "__main__":
    # 初始化并启动服务
    mcp_server = McpServer()
    mcp_server.start()