import os.path
import sys
import threading
import signal
from fastapi import FastAPI
import uvicorn

# 第三方/内部导入
from mcp.server import FastMCP
from config.private.mcp_server.config_loader import McpServerConfig
from oe_cli_mcp_server.common.zip_tool_util import unzip_tool_package
from oe_cli_mcp_server.loader.package_manager import PackageManager, logger
from oe_cli_mcp_server.common.get_project_root import get_project_root

# 全局配置
CONFIG = McpServerConfig().get_config()
FASTAPI_PORT = CONFIG.private_config.fastapi_port
FASTMCP_PORT = CONFIG.private_config.port
TOOLS_PATH = "oe_cli_mcp_server/mcp_tools"

# -------------------------- 核心服务类（继承新版 PackageManager） --------------------------
class McpServer(PackageManager):
    def __init__(self, name="mcp_server", host="0.0.0.0", port=FASTMCP_PORT):
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
        self._fastapi_started = False
        # 注册信号处理（优雅退出）
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    # -------------------------- 资源释放与信号处理 --------------------------
    def release_resources(self):
        """统一释放所有资源"""
        logger.info("开始释放服务资源...")
        # 关闭 FastAPI 服务
        if self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
                if self.fastapi_thread and self.fastapi_thread.is_alive():
                    self.fastapi_thread.join(timeout=3)
                logger.info("FastAPI 服务已关闭")
            except Exception as e:
                logger.error(f"关闭 FastAPI 失败：{str(e)}")
        # 关闭 FastMCP 服务
        if self.mcp:
            try:
                if hasattr(self.mcp, "close"):
                    self.mcp.close()
                elif hasattr(self.mcp, "stop"):
                    self.mcp.stop()
                logger.info("FastMCP 实例已关闭")
            except Exception as e:
                logger.error(f"关闭 FastMCP 失败：{str(e)}")
        # 重置实例
        self.mcp = None
        self.fastapi_app = None
        self.fastapi_thread = None
        self.uvicorn_server = None
        self._fastapi_started = False
        logger.info("资源释放完成")

    def _handle_sigterm(self, signum, frame):
        logger.info(f"收到终止信号（{signum}），准备退出...")
        self.release_resources()
        sys.exit(0)

    # -------------------------- FastAPI 接口（适配新版 PackageManager） --------------------------
    def _create_fastapi_app(self):
        """创建 FastAPI 应用（调整 remove 接口，适配无 venv 逻辑）"""
        app = FastAPI(title="MCP Package API", version="1.0")

        @app.get("/package/list", summary="查询所有已加载工具包")
        def list_packages():
            try:
                pkg_funcs = {}
                sorted_packages = self.list_all_packages()
                for pkg in sorted_packages:
                    sorted_funcs = sorted(self.list_package_funcs(pkg))
                    pkg_funcs[pkg] = sorted_funcs
                return {
                    "success": True,
                    "data": {
                        "pkg_funcs": pkg_funcs,
                        "total_packages": len(pkg_funcs),
                        "total_functions": sum(len(funcs) for funcs in pkg_funcs.values())
                    },
                    "message": "查询成功"
                }
            except Exception as e:
                logger.error(f"查询工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"查询失败：{str(e)}"}

        @app.post("/package/add", summary="添加工具包（支持zip文件）")
        def add_package(value: str):
            try:
                self.load(value)
                return {"success": True, "message": f"添加 {value} 成功（实时生效）"}
            except Exception as e:
                logger.error(f"添加工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"添加失败：{str(e)}"}

        @app.post("/package/remove", summary="删除工具包")
        def remove_package(value: str):
            try:
                self.remove(value)
                # 调整提示：适配无 venv 逻辑，明确仅删除目录
                return {"success": True, "message": f"删除 {value} 成功！需调用 /package/restart 重启服务使修改生效"}
            except Exception as e:
                logger.error(f"删除工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"删除失败：{str(e)}"}

        @app.post("/package/init", summary="初始化工具包（仅保留基础包）")
        def init_package():
            try:
                self.init()
                return {"success": True, "message": "初始化成功（仅保留基础运维包，需重启服务生效）"}
            except Exception as e:
                logger.error(f"初始化失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"初始化失败：{str(e)}"}

        return app

    def _start_fastapi(self):
        """启动 FastAPI 服务（原有逻辑完全保留）"""
        if self._fastapi_started or (self.fastapi_thread and self.fastapi_thread.is_alive()):
            logger.warning("FastAPI 服务已启动，无需重复启动")
            return
        self.fastapi_app = self._create_fastapi_app()

        def run_server():
            try:
                config = uvicorn.Config(
                    self.fastapi_app,
                    host="0.0.0.0",
                    port=FASTAPI_PORT,
                    log_level="warning",
                    access_log=False,
                    reload=False
                )
                self.uvicorn_server = uvicorn.Server(config)
                self.uvicorn_server.run()
            except Exception as e:
                logger.error(f"FastAPI 启动失败：{str(e)}", exc_info=True)
            finally:
                self._fastapi_started = False

        self.fastapi_thread = threading.Thread(target=run_server, daemon=True)
        self.fastapi_thread.start()
        self._fastapi_started = True
        logger.info(f"FastAPI 服务启动：http://0.0.0.0:{FASTAPI_PORT}/docs")

    # -------------------------- 工具注册逻辑（适配新版 Tool 模型） --------------------------
    def _register_single_package_tools(self, package_name: str):
        """注册单个包的工具函数（适配新版 Tool 模型）"""
        registered_count = 0
        # 遍历该包下的所有函数并注册
        for func_name in sorted(self.list_package_funcs(package_name)):
            func_info = self.get_tool_func_info(func_name)
            if not func_info:
                logger.warning(f"函数 {func_name} 不存在，跳过注册")
                continue
            # 直接使用 Tool 模型的 description 字段（已适配语言）
            desc = func_info.description
            # 核心注册逻辑
            self.mcp.tool(name=func_name, description=desc)(func_info.func)
            registered_count += 1
        logger.info(f"包 {package_name} 注册 {registered_count} 个工具函数")

    def _register_all_tools(self):
        """统一注册所有工具（适配新版 Tool 模型）"""
        registered_count = 0
        sorted_packages = self.list_all_packages()
        for pkg in sorted_packages:
            sorted_funcs = sorted(self.list_package_funcs(pkg))
            for func_name in sorted_funcs:
                func_info = self.get_tool_func_info(func_name)
                if not func_info:
                    logger.warning(f"函数 {func_name} 不存在，跳过注册")
                    continue
                # 直接使用 Tool 模型的 description 字段
                desc = func_info.description
                self.mcp.tool(name=func_name, description=desc)(func_info.func)
                registered_count += 1
        logger.info(f"工具注册完成：共注册 {registered_count} 个函数（{len(sorted_packages)} 个包）")

    # -------------------------- 核心业务方法（适配新版 PackageManager + UV + requirements.txt） --------------------------
    def load(self, mcp_collection: None | str = None):
        """加载工具包（核心修改：注释适配 UV + requirements.txt，逻辑完全不变）"""
        try:
            if mcp_collection is None:
                self.load_all_packages()
                self._register_all_tools()
                logger.info("加载所有工具包成功（实时生效）")
                return

            if mcp_collection and mcp_collection.endswith(".zip"):
                unzip_tool_package(mcp_collection)
                pkg_name = os.path.basename(mcp_collection)[:-4]
                pkg_dir = os.path.join(get_project_root(), TOOLS_PATH, pkg_name)

                if pkg_name in self.list_all_packages():
                    logger.warning(f"包 {pkg_name} 已加载或路径无效，跳过")
                    return

                if not self.load_package(pkg_dir):
                    logger.error(f"加载包{pkg_name}目录 {pkg_dir} 失败")
                    return

            else:
                pkg_dir = os.path.abspath(mcp_collection)
                pkg_name = os.path.basename(pkg_dir)

                if pkg_name in self.list_all_packages():
                    logger.warning(f"包 {pkg_name} 已加载，跳过")
                    return

                if not self.load_package(pkg_dir):
                    logger.error(f"加载包目录 {pkg_dir} 失败")
                    return

            self._register_single_package_tools(pkg_name)
            logger.info(f"加载成功：当前共 {len(self.list_all_packages())} 个包（实时生效）")

        except Exception as e:
            logger.error(f"加载 {mcp_collection} 失败：{str(e)}", exc_info=True)
            raise

    def remove(self, mcp_collection):
        """卸载工具包（适配新版 PackageManager，移除 venv 相关参数）"""
        try:
            pkg_name = mcp_collection
            if pkg_name not in self.list_all_packages():
                logger.warning(f"包 {pkg_name} 不存在，无需卸载")
                return

            # 适配新版 unload_package：仅保留 delete_dir 参数，删除 delete_env
            self.unload_package(pkg_name, delete_dir=True)

            # 清理模块缓存（可选，重启会自动清理）
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith(f"package_{pkg_name}_") or mod_name.startswith(f"{pkg_name}."):
                    del sys.modules[mod_name]
                    logger.debug(f"清理模块缓存：{mod_name}")

            logger.info(f"删除成功：已卸载 {pkg_name} 包（仅删除物理目录），需重启服务使修改生效")

        except Exception as e:
            logger.error(f"卸载 {mcp_collection} 失败：{str(e)}", exc_info=True)
            raise

    def init(self):
        """初始化工具包（适配新版 PackageManager，移除 venv 逻辑）"""
        logger.info("开始初始化工具包...")
        base_packages_dir = os.path.join(get_project_root(), TOOLS_PATH)

        if os.path.exists(base_packages_dir):
            module_prefixes = [
                dir_name for dir_name in os.listdir(base_packages_dir)
                if os.path.isdir(os.path.join(base_packages_dir, dir_name))
                   and not dir_name.startswith(".")
            ]
            # 清理模块缓存
            for mod_name in list(sys.modules.keys()):
                if any(
                        mod_name == prefix or mod_name.startswith(f"{prefix}.") or mod_name.startswith(f"package_{prefix}_")
                        for prefix in module_prefixes
                ):
                    del sys.modules[mod_name]
                    logger.debug(f"清理模块缓存：{mod_name}")
        else:
            logger.warning(f"工具包根目录不存在：{base_packages_dir}，跳过模块缓存清理")

        # 重置服务并重新加载
        self.release_resources()
        self.mcp = FastMCP(self.name, host=self.host, port=self.port)
        self.load()
        logger.info("初始化完成（需重启服务生效）")

    def reload_config(self):
        """补充reload_config方法（适配原有调用）"""
        global CONFIG
        CONFIG = McpServerConfig().get_config()
        self.language = CONFIG.public_config.language
        self.port = CONFIG.private_config.port

    def restart(self):
        """重启服务（原有逻辑不变）"""
        logger.info("重启 MCP 服务...")
        self.release_resources()
        self.start()

    def start(self):
        """启动核心服务（原有逻辑不变）"""
        logger.info("启动 MCP 服务...")
        if not self.mcp:
            self.mcp = FastMCP(self.name, host=self.host, port=self.port)

        self.load()
        self._start_fastapi()

        logger.info(f"FastMCP 服务启动：{self.host}:{self.port}")
        try:
            self.mcp.run(transport='sse')
        except Exception as e:
            logger.error(f"FastMCP 服务运行失败：{str(e)}", exc_info=True)
            self.release_resources()
            sys.exit(1)

