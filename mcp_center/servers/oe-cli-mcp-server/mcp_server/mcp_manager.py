# mcp_server/server.py
import os.path
from functools import wraps
from mcp.server import FastMCP
from config.base_config_loader import BaseConfig
from mcp_server.manager.manager import ToolManager, logger
from mcp_tools.tool_type import ToolType
from util.get_project_root import get_project_root
from util.zip_tool_util import unzip_tool
import threading
import uvicorn
from fastapi import FastAPI

# -------------------------- 导入独立的 FastAPI 启动函数 --------------------------


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
        self.fastapi_app = None  # 存储 FastAPI 实例
        self.fastapi_thread = None  # 存储 FastAPI 线程

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
            logger.info(f"包名：{pkg}")
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

        all_types = self.list_tool_types()
        for mcp_type in all_types:
            self.unload_tool_type(mcp_type)
        BaseConfig().update_config(default=True)
        self.reload_config()
        del self.mcp
        self.mcp = FastMCP("mcp实例", host=self.host, port=self.port)
        self.load(ToolType.BASE)
        logger.info(f"初始化完成：仅保留基础运维包,重启后生效")

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

    def start(self):

        # 1. 先初始化 MCP 核心逻辑（确保 self.list_packages 等方法可用）
        self.restore_tool_state()
        self.reload_package_functions()
        for pkg in self.list_packages():
            logger.info(f"包名：{pkg}")
            self.load(pkg)
        logger.info(f"MCP 实例初始化完成，已加载 {len(self.list_packages())} 个工具包")

        # 2. 启动 FastAPI 服务（直接调用实例方法，绑定 self）
        self._start_fastapi(host="0.0.0.0", port=8003)

        # 3. 最后启动 FastMCP 主服务（阻塞主线程）
        logger.info("启动 FastMCP 主服务...")
        self.mcp.run(transport='sse')

    # -------------------------- 简化 start 方法：调用独立的 FastAPI 启动函数 --------------------------

    def _create_fastapi_app(self):
        """创建 FastAPI 应用（内部方法，绑定当前实例 self）"""
        app = FastAPI(title="MCP Tool API", version="1.0")

        # -------------------------- FastAPI 接口（完全对齐 Socket 版本逻辑）--------------------------
        @app.get("/tool/list", summary="查询所有已加载工具包")
        def list_tools():
            """查询工具包（直接用 self 调用 list_packages/list_funcs，与 Socket list 逻辑一致）"""
            try:
                # 直接用 self 调用实例方法（和 Socket 版本 _exec_socket_action 的 list 逻辑完全一致）
                pkg_funcs = {}
                for pkg in self.list_packages():
                    pkg_funcs[pkg] = self.list_funcs(pkg)
                return {
                    "success": True,
                    "data": {
                        "pkg_funcs": pkg_funcs,
                        "total_packages": len(pkg_funcs)  # 适配 handle.py 预期的返回结构
                    }
                }
            except Exception as e:
                logger.error(f"查询工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"查询失败：{str(e)}"}

        @app.post("/tool/add", summary="添加工具包")
        def add_tool(type: str, value: str):
            """添加系统/自定义工具包（与 Socket add 逻辑完全一致）"""
            try:
                # 完全对齐 _exec_socket_action 的 add 逻辑
                if type == "system":
                    self.load(ToolType(value))  # 系统包：按 ToolType 加载
                else:  # custom 类型
                    self.load(value)  # 自定义包：按 zip 路径加载
                return {"success": True, "message": f"新增{value}成功"}
            except Exception as e:
                logger.error(f"添加工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"添加失败：{str(e)}"}

        @app.post("/tool/remove", summary="删除工具包")
        def remove_tool(type: str, value: str):
            """删除工具包"""
            try:
                # 完全对齐 _exec_socket_action 的 remove 逻辑
                if type == "system":
                    self.remove(ToolType(value))  # 系统包：按 ToolType 删除
                else:  # custom 类型
                    self.remove(value)  # 自定义包：按包名/路径删除
                return {"success": True, "message": f"删除{value}成功,重启后生效"}
            except Exception as e:
                logger.error(f"删除工具包 {value} 失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"删除失败：{str(e)}"}

        @app.post("/tool/init", summary="初始化工具包")
        def init_tool():
            """初始化工具包"""
            try:
                self.init()  # 直接调用实例的 init 方法（和 Socket 版本一致）
                return {"success": True, "message": "初始化成功（仅保留基础运维包）重启后生效"}
            except Exception as e:
                logger.error(f"初始化工具包失败：{str(e)}", exc_info=True)
                return {"success": False, "message": f"初始化失败：{str(e)}"}

        return app

    def _start_fastapi(self, host: str = "0.0.0.0", port: int = 8003):
        """启动 FastAPI 服务（实例方法，直接绑定 self）"""
        # 1. 创建 FastAPI 应用（绑定当前实例）
        self.fastapi_app = self._create_fastapi_app()
        logger.info(f"FastAPI 应用创建完成，接口文档：http://{host}:{port}/docs")

        # 2. 定义线程内运行的服务逻辑
        def run_server():
            try:
                uvicorn.run(
                    self.fastapi_app,
                    host=host,
                    port=port,
                    log_level="warning",
                    access_log=False
                )
            except Exception as e:
                logger.error(f"FastAPI 服务启动失败：{str(e)}", exc_info=True)

        # 3. 启动独立线程（不阻塞主服务）
        self.fastapi_thread = threading.Thread(target=run_server, daemon=True)
        self.fastapi_thread.start()
        logger.info(f"FastAPI 服务线程启动成功（线程ID：{self.fastapi_thread.ident}）")


# -------------------------- 启动服务（原有逻辑不变）--------------------------
if __name__ == "__main__":
    config = BaseConfig().get_config().public_config
    mcp_server = McpServer("MCP_Tool_Service", config.host, config.port)
    mcp_server.start()