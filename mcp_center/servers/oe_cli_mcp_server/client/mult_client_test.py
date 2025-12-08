import asyncio
import time

from mcp_center.servers.oe_cli_mcp_server.client.client import MCPClient

# 替换为你的 MCPClient 真实导入路径


# 压测基础配置
CLIENT_NUM = 10  # 10个客户端
PRESSURE_TIME = 600  # 压测10分钟（600秒）
MCP_URL = "http://0.0.0.0:12555/sse"
MCP_HEADERS = {}
TOOL_PARAMS = {"info_types": ["cpu", "mem", "disk", "os"]}

# 单个客户端初始化
async def init_single_client(client_id):
    """初始化1个客户端并返回实例"""
    try:
        client = MCPClient(MCP_URL, MCP_HEADERS)
        await client.init()
        print(f"客户端{client_id} 初始化成功")
        return client
    except Exception as e:
        print(f"客户端{client_id} 初始化失败：{e}")
        return None

# 单个客户端压测任务（持续发请求）
async def single_client_pressure(client_id, client):
    """1个客户端持续压测，直到达到时长"""
    if not client:
        return
    start_time = time.time()
    req_count = 0  # 记录该客户端请求次数
    print(f"客户端{client_id} 开始压测")

    # 持续压测：直到超过设定时间
    while time.time() - start_time < PRESSURE_TIME:
        try:
            # 发送工具调用请求（串行，适配客户端单连接）
            await client.call_tool("sys_info_tool", TOOL_PARAMS)
            req_count += 1
        except Exception as e:
            print(f"客户端{client_id} 请求失败：{e}")
        # 可选：若MCP扛不住，加微小间隔（如0.001秒），默认无间隔
        # await asyncio.sleep(0.001)

    # 单个客户端压测结束
    print(f"客户端{client_id} 压测结束，总请求数：{req_count}")

# 主逻辑：初始化10个客户端+并发压测
async def main():
    print(f"开始初始化 {CLIENT_NUM} 个客户端...")

    # 1. 批量初始化10个客户端
    clients = []
    for i in range(1, CLIENT_NUM + 1):
        client = await init_single_client(i)
        if client:
            clients.append((i, client))

    # 若客户端初始化失败，提示并退出
    if len(clients) < CLIENT_NUM:
        print(f"仅 {len(clients)} 个客户端初始化成功，开始压测...")
    else:
        print(f"{CLIENT_NUM} 个客户端全部初始化成功，开始压测（持续{int(PRESSURE_TIME/60)}分钟）...")

    # 2. 启动所有客户端的压测任务（并发执行）
    pressure_tasks = []
    for client_id, client in clients:
        task = asyncio.create_task(single_client_pressure(client_id, client))
        pressure_tasks.append(task)

    # 3. 等待所有压测任务完成（直到10分钟）
    await asyncio.gather(*pressure_tasks)
    print("所有客户端压测结束！")

if __name__ == "__main__":
    asyncio.run(main())