from typing import Any
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import urllib.parse
from bson import ObjectId
from pydantic import BaseModel, Field, HttpUrl
# 假设 PermissionType 已经在别处定义


class PermissionType(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"

# 定义模型类


class PoolBase(BaseModel):
    id: str = Field(alias='_id')
    name: str
    description: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=timezone.utc).timestamp(), 3))


class ServiceApiInfo(BaseModel):
    filename: str
    description: str
    path: str


class Permission(BaseModel):
    type: PermissionType = Field(description="权限类型", default=PermissionType.PRIVATE)
    users: list[str] = Field(description="可访问的用户列表", default=[])


class ServicePool(PoolBase):
    author: str
    api: list[ServiceApiInfo] = Field(description="API信息列表", default=[])
    permissions: Optional[Permission] = Field(description="用户与服务的权限关系", default=None)
    favorites: list[str] = Field(description="收藏此应用的用户列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值；Service作为整体更新或删除", default={})


# MongoDB配置
# config = {
#     'MONGODB_USER': 'admin',
#     'MONGODB_PWD': '123456',
#     'MONGODB_HOST': '0.0.0.0',
#     'MONGODB_PORT': '27021',
#     'MONGODB_DATABASE': 'test_database'
# }
# MongoDB配置
config = {
    'MONGODB_USER': 'euler_copilot',
    'MONGODB_PWD': '8URM%HtCHQPxKe$u',
    'MONGODB_HOST': '10.43.208.180',
    'MONGODB_PORT': '27017',
    'MONGODB_DATABASE': 'euler_copilot'
}


class MongoDB:
    _client = MongoClient(
        f"mongodb://{urllib.parse.quote_plus(config['MONGODB_USER'])}:{urllib.parse.quote_plus(config['MONGODB_PWD'])}@{config['MONGODB_HOST']}:{config['MONGODB_PORT']}/?directConnection=true",
    )

    @classmethod
    def get_collection(cls, collection_name: str):
        try:
            return cls._client[config["MONGODB_DATABASE"]][collection_name]
        except Exception as e:
            print(f"Get collection {collection_name} failed: {e}")
            raise RuntimeError(str(e)) from e


async def insert_service_pool():
    # 示例数据
    api_info_1 = ServiceApiInfo(filename="example_1.yaml", description="Example API 1", path="/api/example/3")
    api_info_2 = ServiceApiInfo(filename="example_2.yaml", description="Example API 2", path="/api/example/2")
    api_info_3 = ServiceApiInfo(filename="example_3.yaml", description="Example API 3", path="/api/example/1")
    id = "6a08c845-abdc-45fb-853e-54a806437dab"
    print(id)
    service_pool_sys = ServicePool(
        _id=id,
        name="系统",
        description="系统函数",
        author="test",
        api=[api_info_1, api_info_2, api_info_3],
        permissions=Permission(type=PermissionType.PUBLIC.value, users=["user1", "user2"]).dict(),
        favorites=["user1","test"],
        hashes={"file1": "hash1", "file2": "hash2"}
    )
    id = str(uuid.uuid4())
    print(id)
    service_pool_a_ops = ServicePool(
        _id=id,
        name="a-ops-apollo",
        description="a-ops下cve相关组件",
        author="test",
        api=[api_info_1, api_info_2, api_info_3],
        permissions=Permission(type=PermissionType.PUBLIC.value, users=["user1", "user2"]).dict(),
        favorites=["user1"],
        hashes={"file1": "hash1", "file2": "hash2"}
    )
    """插入ServicePool实例到MongoDB"""
    collection = MongoDB.get_collection('service')
    result = collection.delete_many({})
    # 将Pydantic模型转换为字典并插入到MongoDB中
    try:
        result = collection.update_one(
            {'_id': service_pool_sys.id},  # 查找条件
            {"$set": service_pool_sys.dict(by_alias=True)},  # 更新操作
            upsert=True  # 如果不存在则插入新文档
        )
        result = collection.update_one(
            {'_id': service_pool_a_ops.id},  # 查找条件
            {"$set": service_pool_a_ops.dict(by_alias=True)},  # 更新操作
            upsert=True  # 如果不存在则插入新文档
        )
        print(f"Inserted document with id: {result.upserted_id}")
    except PyMongoError as e:
        print(f"An error occurred while inserting the document: {e}")


class NodePool(PoolBase):
    """Node信息

    collection: node
    注：
        1. 基类Call的ID，即meta_call，可以为None，表示该Node是系统Node
        2. 路径的格式：
            1. 系统Node的路径格式样例：“LLM”
            2. Python Node的路径格式样例：“tune::call.tune.CheckSystem”
    """

    id: str = Field(description="Node的ID", default_factory=lambda: str(uuid.uuid4()), alias="_id")
    service_id: str = Field(description="Node所属的Service ID")
    call_id: str = Field(description="所使用的Call的ID")
    fixed_params: dict[str, Any] = Field(description="Node的固定参数", default={})
    params_schema: dict[str, Any] = Field(description="Node的参数schema；只包含用户可以改变的参数", default={})
    output_schema: dict[str, Any] = Field(description="Node的输出schema；做输出的展示用", default={})


async def insert_node_pool():  
    collection = MongoDB.get_collection('node')
    result = collection.delete_many({})  # 清空集合中的所有文档（仅用于演示）
    node_pools = [NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="knowledge_base",  # 随机生成一个 call_id
        name="【KNOWLEDGE】知识库",  # 提供名称
        description="支持知识库中文档的查询",  # 提供描述
        params_schema={
            "search_methods": [],
            "rerank_methods": [],
            "konwledge_base_id": "",
            "query": "",
            "top_k": 0},
        output_schema={"content": {"type":"string", "description": "回答"}}
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="LLM",  # 随机生成一个 call_id
        name="【LLM】大模型",  # 提供名称
        description="大模型调用",  # 提供描述
        params_schema={
            "base_url": "",
            "api_key": "",
            "max_tokens": 0,
            "is_stream": True,
            "prompt": "",
            "temperature": 0},
        output_schema={"content": {}}
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="choice",  # 随机生成一个 call_id
        name="【LLM】意图识别",  # 提供名称
        description="利用大模型能力选择分支",  # 提供描述
        params_schema={
                "choices": [
                    {
                        "branchId": "source_a",
                        "description": "IF A",
                        "purpose": "",
                        "variable_a": "",
                    },
                    {
                        "branchId": "source_b",
                        "description": "ELSE B",
                    },
                ],
        },
        output_schema={
            "type":"object",
            "properties": {
                "content": {
                    "type":"string",
                    "description": "回答",
                },
            },
        }
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="choice",  # 随机生成一个 call_id
        name="【CHOICE】条件分支",  # 提供名称
        description="条件分支节点",  # 提供描述
        params_schema={
                       "choices": [
                            {
                                "branchId":"source_a",
                                "description":"IF A",
                                "operator":"",
                                "variable_a":"",
                                "variable_b":"",
                            },
                            {
                                "branchId":"source_b",
                                "description":"ELSE B",
                            },
                        ],
                },
        output_schema={}
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="loop_begin",  # 随机生成一个 call_id
        name="【LOOP】循环开始节点",  # 提供名称
        description="",  # 提供描述
        params_schema={"operation_exp": {}},
        output_schema={},
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="loop_begin",  # 随机生成一个 call_id
        name="【LOOP】循环结束节点",  # 提供名称
        description="",  # 提供描述
        params_schema={"operation_exp": {}},
        output_schema={},
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6a08c845-abdc-45fb-853e-54a806437dab",  # 使用 "test" 作为 service_id
        call_id="template_exchange",  # 随机生成一个 call_id
        name="【LLM】模板转换",  # 提供名称
        description="This is an example node pool for demonstration purposes.",  # 提供描述
        params_schema={"input_schema": {},
                       "exchange_rule": [{}]},
        output_schema={
            "type":"object",
            "properties": {
                "output_schema": {
                    "type":"object",
                    "description": "嵌套字典结构",
                    "properties": {
                        "content": {
                            "type":"string",
                            "description": "回答",
                        },
                        "task_id": {
                            "type":"string",
                            "description": "任务ID",
                        }
                    },
                },
            },
        },
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6d7f65ff-55de-4206-9e5b-87aa2b529bd4",  # 使用 "test" 作为 service_id
        call_id="search",  # 随机生成一个 call_id
        name="【API】扫描CVE漏洞",  # 提供名称
        description="扫描某个机器所有的CVE漏洞",  # 提供描述
        params_schema={"host": ""},
        output_schema={"task_id": ""},
    ), NodePool(
        _id=str(uuid.uuid4()),  # 自动生成一个唯一的 ID
        service_id="6d7f65ff-55de-4206-9e5b-87aa2b529bd4",  # 使用 "test" 作为 service_id
        call_id="search",  # 随机生成一个 call_id
        name="【API】修复CVE漏洞",  # 提供名称
        description="修复某个机器上的CVE漏洞",  # 提供描述
        params_schema={"host": "",
                       "cve_id": ""},
        output_schema={"task_report":{}},
    )
    ]
    collection = MongoDB.get_collection('node')
    result = collection.delete_many({})
    # 将 NodePool 模型转换为字典并插入到 MongoDB 中
    try:
        import time
        for node_pool in node_pools:
            time.sleep(1)
            print(node_pool.service_id)
            result = collection.update_one(
                {'_id': node_pool.id},  # 查找条件，这里假设 _id 即为 node_pool.id
                {"$set": node_pool.dict(by_alias=True)},  # 更新操作
                upsert=True  # 如果不存在则插入新文档
            )
            print("updata success")
            print(result.upserted_id)

        return result.upserted_id or node_pool.id  # 返回插入或更新的文档ID
    except PyMongoError as e:
        print(f"An error occurred while inserting the document: {e}")
        raise  # 或者根据需要选择是否重新抛出异常


class Permission(BaseModel):
    """App的权限配置"""

    type: PermissionType = Field(
        description="权限类型", default=PermissionType.PRIVATE)
    users: list[str] = Field(description="可访问的用户列表", default=[])


class PositionItem(BaseModel):
    """请求/响应中的前端相对位置变量类"""
    x: float
    y: float


class AppFlow(PoolBase):
    """Flow的元数据；会被存储在App下面"""

    enabled: bool = Field(description="是否启用", default=True)
    path: str = Field(description="Flow的路径")
    focus_point: PositionItem = Field(
        description="Flow的视觉焦点", default=PositionItem(x=0, y=0))


class AppLink(BaseModel):
    """App的相关链接"""

    title: str = Field(description="链接标题")
    url: str = Field(..., description="链接地址")


class AppPool(PoolBase):
    """应用信息

    collection: app
    """

    author: str = Field(description="作者的用户ID")
    type: str = Field(description="应用类型", default="default")
    icon: str = Field(description="应用图标")
    published: bool = Field(description="是否发布", default=False)
    links: list[AppLink] = Field(description="相关链接", default=[])
    first_questions: list[str] = Field(description="推荐问题", default=[])
    history_len: int = Field(3, ge=1, le=10, description="对话轮次（1～10）")
    permission: Permission = Field(
        description="应用权限配置", default=Permission(type=PermissionType.PRIVATE.value, users=[]))
    flows: list[AppFlow] = Field(description="Flow列表", default=[])
    favorites: list[str] = Field(description="收藏此应用的用户列表", default=[])
    hashes: dict[str, str] = Field(description="关联文件的hash值", default={})


async def insert_app_pool():
    collection = MongoDB.get_collection('app')
    result = collection.delete_many({})  # 清空集合中的所有文档（仅用于演示）
    return
    app_pool = AppPool(
        _id="test",  # 自动生成一个唯一的 ID
        author="test",  # 使用 "author_id" 作为作者ID
        name="Example App Pool ",  # 提供名称
        description="This is my test ",  # 提供描述
        published=False,
        icon="icon_url",  # 提供图标URL
        type="example_type",  # 提供应用类型
        links=[AppLink(title="Example Link", url="http://example.com")],  # 提供相关链接列表
        first_questions=["What is your name?", "How are you?"],  # 提供推荐问题列表
        history_len=5,  # 设置对话轮次
        permission=Permission(type=PermissionType.PUBLIC, users=["user1", "user2"]),  # 设置权限配置
        flows=[AppFlow(
            _id="test",  # 提供一个唯一的标识符
            name="Main Flow",             # 提供一个名称
            description="Description of the main flow",  # 提供描述
            path="main_flow",
            focus_point=PositionItem(x=0.5, y=0.5)
        )],  # 添加Flows
        favorites=["user3", "user4"],  # 收藏此应用的用户列表
        hashes={"file1": "hash1", "file2": "hash2"}  # 关联文件的hash值
    )
    collection.update_one(
        {'_id': app_pool.id},  # 查找条件，这里假设 _id 即为 app_pool.id
        {"$set": app_pool.dict(by_alias=True)},  # 更新操作
        upsert=True  # 如果不存在则插入新文档
    )
    for i in range(100):
        print(i)
        app_pool = AppPool(
            _id="my_test_"+str(i),  # 自动生成一个唯一的 ID
            author="test",  # 使用 "author_id" 作为作者ID
            name="Example App Pool "+str(i),  # 提供名称
            description="This is my test "+str(i),  # 提供描述
            published=i % 2,
            icon="icon_url",  # 提供图标URL
            type="example_type",  # 提供应用类型
            links=[AppLink(title="Example Link", url="http://example.com")],  # 提供相关链接列表
            first_questions=["What is your name?", "How are you?"],  # 提供推荐问题列表
            history_len=5,  # 设置对话轮次
            permission=Permission(type=PermissionType.PUBLIC, users=["user1", "user2"]),  # 设置权限配置
            flows=[AppFlow(
                _id="test",  # 提供一个唯一的标识符
                name="Main Flow",             # 提供一个名称
                description="Description of the main flow",  # 提供描述
                path="main_flow",
                focus_point=PositionItem(x=0.5, y=0.5)
            )],  # 添加Flows
            favorites=["user3", "user4"],  # 收藏此应用的用户列表
            hashes={"file1": "hash1", "file2": "hash2"}  # 关联文件的hash值
        )

        # 将 AppPool 模型转换为字典并插入到 MongoDB 中
        try:
            result = collection.update_one(
                {'_id': app_pool.id},  # 查找条件，这里假设 _id 即为 app_pool.id
                {"$set": app_pool.dict(by_alias=True)},  # 更新操作
                upsert=True  # 如果不存在则插入新文档
            )
            print(f"Inserted or updated document with id: {app_pool.id}")
        except PyMongoError as e:
            print(f"An error occurred while inserting the document: {e}")
            raise  # 或者根据需要选择是否重新抛出异常
    for i in range(100):
        print(i)
        app_pool = AppPool(
            _id="test_"+str(i),  # 自动生成一个唯一的 ID
            author="test_"+str(i),  # 使用 "author_id" 作为作者ID
            name="Example App Pool",  # 提供名称
            description="This is test "+str(i),  # 提供描述
            published=i % 2,
            icon="icon_url",  # 提供图标URL
            type="example_type",  # 提供应用类型
            links=[AppLink(title="Example Link", url="http://example.com")],  # 提供相关链接列表
            first_questions=["What is your name?", "How are you?"],  # 提供推荐问题列表
            history_len=5,  # 设置对话轮次
            permission=Permission(type=PermissionType.PUBLIC, users=["user1", "user2"]),  # 设置权限配置
            flows=[AppFlow(
                _id="test",  # 提供一个唯一的标识符
                name="Main Flow",             # 提供一个名称
                description="Description of the main flow",  # 提供描述
                path="main_flow",
                focus_point=PositionItem(x=0.5, y=0.5)
            )],  # 添加Flows
            favorites=["user3", "user4"],  # 收藏此应用的用户列表
            hashes={"file1": "hash1", "file2": "hash2"}  # 关联文件的hash值
        )

        # 将 AppPool 模型转换为字典并插入到 MongoDB 中
        try:
            result = collection.update_one(
                {'_id': app_pool.id},  # 查找条件，这里假设 _id 即为 app_pool.id
                {"$set": app_pool.dict(by_alias=True)},  # 更新操作
                upsert=True  # 如果不存在则插入新文档
            )
            print(f"Inserted or updated document with id: {app_pool.id}")
        except PyMongoError as e:
            print(f"An error occurred while inserting the document: {e}")
            raise  # 或者根据需要选择是否重新抛出异常


def query_all_target(tag:str):
    """查询所有插入到MongoDB中的node数据"""
    collection = MongoDB.get_collection(tag)
    try:
        nodes = list(collection.find({}))
        for node in nodes:
            print(node)
    except PyMongoError as e:
        print(f"An error occurred while querying the documents: {e}")

# 使用 asyncio 运行异步函数
if __name__ == "__main__":
    # asyncio.run(insert_node_pool())
    asyncio.run(insert_service_pool())
    query_all_target("node")