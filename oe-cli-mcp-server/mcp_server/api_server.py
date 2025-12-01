# mcp_server/api_server.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn
import threading
import logging

# 导入单例 McpServer（用于调用核心业务逻辑）
from mcp_server.server import McpServer
from mcp_tools.tool_type import ToolType

# 日志配置（与主服务保持一致）
logger = logging.getLogger("McpApiServer")

# -------------------------- FastAPI 初始化 --------------------------
def create_fastapi_app() -> FastAPI:
    """创建 FastAPI 实例并定义接口（独立于 McpServer 类）"""
    app = FastAPI(
        title="MCP Tool Manager API",
        description="用于管理 MCP 工具包的 HTTP 接口（替代原 Socket 服务）",
        version="1.0.0"
    )

    # -------------------------- 数据模型（参数校验）--------------------------
    class AddToolRequest(BaseModel):
        type: str = Query(..., description="工具类型：system（系统包）/ custom（自定义包）")
        value: str = Query(..., description="系统包填 ToolType 值，自定义包填 zip 路径或包名")

    class RemoveToolRequest(BaseModel):
        type: str = Query(..., description="工具类型：system（系统包）/ custom（自定义包）")
        value: str = Query(..., description="系统包填 ToolType 值，自定义包填包名")

    # -------------------------- 核心：获取 McpServer 单例实例 --------------------------
    def get_mcp_server() -> McpServer:
        """获取 McpServer 单例（确保与主服务使用同一个实例）"""
        try:
            return McpServer._instance  # 直接获取单例（依赖原 singleton 装饰器的 _instance 属性）
        except AttributeError:
            raise HTTPException(status_code=503, detail="MCP 主服务未初始化")

    # -------------------------- API 接口定义 --------------------------
    @app.post("/tool/add", summary="新增工具包")
    def add_tool(type: str = Query(...), value: str = Query(...)):
        """新增工具包（system/custom 类型）"""
        mcp_server = get_mcp_server()
        try:
            if type == "system":
                # 转换为 ToolType 枚举
                try:
                    tool_type = ToolType(value)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"不支持的系统工具类型：{value}（参考 ToolType 枚举）")
                mcp_server.load(tool_type)
            elif type == "custom":
                mcp_server.load(value)
            else:
                raise HTTPException(status_code=400, detail="type 只能是 system 或 custom")
            return {"success": True, "message": f"新增 {value} 成功"}
        except HTTPException:
            raise  # 直接抛出已定义的 HTTP 异常
        except Exception as e:
            logger.error(f"新增工具包失败：{str(e)}")
            raise HTTPException(status_code=500, detail=f"新增失败：{str(e)}")

    @app.post("/tool/remove", summary="删除工具包")
    def remove_tool(type: str = Query(...), value: str = Query(...)):
        """删除工具包（system/custom 类型）"""
        mcp_server = get_mcp_server()
        try:
            if type == "system":
                try:
                    tool_type = ToolType(value)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"不支持的系统工具类型：{value}")
                mcp_server.remove(tool_type)
            elif type == "custom":
                mcp_server.remove(value)
            else:
                raise HTTPException(status_code=400, detail="type 只能是 system 或 custom")
            return {"success": True, "message": f"删除 {value} 成功，重启后生效"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除工具包失败：{str(e)}")
            raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")

    @app.get("/tool/list", summary="查询所有已加载工具包")
    def list_tools():
        """查询所有工具包及对应的函数"""
        mcp_server = get_mcp_server()
        try:
            pkg_funcs = {}
            for pkg in mcp_server.list_packages():
                pkg_funcs[pkg] = mcp_server.list_funcs(pkg)
            return {
                "success": True,
                "data": {
                    "pkg_funcs": pkg_funcs,
                    "total_packages": len(pkg_funcs)
                }
            }
        except Exception as e:
            logger.error(f"查询工具包失败：{str(e)}")
            raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")

    @app.post("/tool/init", summary="初始化系统（仅保留基础运维包）")
    def init_system():
        """初始化系统，卸载所有包并仅保留基础运维包"""
        mcp_server = get_mcp_server()
        try:
            mcp_server.init()
            return {"success": True, "message": "初始化成功（仅保留基础运维包）"}
        except Exception as e:
            logger.error(f"初始化系统失败：{str(e)}")
            raise HTTPException(status_code=500, detail=f"初始化失败：{str(e)}")

    @app.post("/tool/restart", summary="重启 MCP 服务")
    def restart_service():
        """重启 MCP 服务（重新加载所有工具包）"""
        mcp_server = get_mcp_server()
        try:
            mcp_server.restart()
            return {"success": True, "message": "服务重启成功"}
        except Exception as e:
            logger.error(f"重启服务失败：{str(e)}")
            raise HTTPException(status_code=500, detail=f"重启失败：{str(e)}")

    return app

# -------------------------- 启动 FastAPI 服务（独立线程）--------------------------
def start_fastapi_server(host: str = "0.0.0.0", port: int = 8003):
    """在独立线程中启动 FastAPI 服务（不阻塞主服务）"""
    app = create_fastapi_app()
    logger.info(f"FastAPI 服务启动中：http://{host}:{port}")
    logger.info(f"接口文档地址：http://{host}:{port}/docs")

    def run_server():
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",  # 仅输出警告以上日志
            access_log=False      # 关闭访问日志（避免刷屏）
        )

    # 启动独立线程（daemon=True：主进程退出时，API 服务也退出）
    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()
    return api_thread