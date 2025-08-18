"""MessageQueue单元测试"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.common.queue import MessageQueue
from apps.schemas.enum_var import EventType
from apps.schemas.message import HeartbeatData, MessageBase, MessageFlow, MessageMetadata
from apps.schemas.task import Task


@pytest.fixture
def message_queue():
    """测试fixture: 初始化MessageQueue"""
    return MessageQueue()


@pytest.fixture
def mock_task():
    """测试fixture: mock Task对象"""
    task = MagicMock(spec=Task)
    task.id = "test_task_id"
    task.ids.record_id = "record_id"
    task.ids.group_id = "group_id"
    task.ids.conversation_id = "conversation_id"
    task.tokens.time = 0
    task.tokens.input_delta = 10
    task.tokens.output_delta = 20
    task.state = None
    return task


@pytest.mark.asyncio
async def test_init(message_queue):
    """测试初始化队列"""
    task_id = "test_task"
    await message_queue.init(task_id)
    assert message_queue._task_id == task_id
    assert not message_queue._close
    assert message_queue._heartbeat_task is not None


@pytest.mark.asyncio
async def test_push_output_with_done(message_queue, mock_task):
    """测试推送DONE消息"""
    await message_queue.init("test_task")
    await message_queue.push_output(mock_task, EventType.DONE, {})
    assert await message_queue._queue.get() == "[DONE]"


@pytest.mark.asyncio
async def test_push_output_normal(message_queue, mock_task):
    """测试推送普通消息"""
    await message_queue.init("test_task")
    test_data = {"key": "value"}
    await message_queue.push_output(mock_task, EventType.TEXT_ADD, test_data)
    
    message_str = await message_queue._queue.get()
    message = json.loads(message_str)
    
    assert message["event"] == "text.add"
    assert message["content"] == test_data
    assert message["metadata"]["inputTokens"] == 10
    assert message["metadata"]["outputTokens"] == 20


@pytest.mark.asyncio
async def test_push_output_with_flow(message_queue, mock_task):
    """测试推送带Flow的消息"""
    mock_task.state = MagicMock()
    mock_task.state.app_id = "app_id"
    mock_task.state.flow_id = "flow_id"
    mock_task.state.step_id = "step_id"
    mock_task.state.step_name = "step_name"
    mock_task.state.step_status = "running"
    
    await message_queue.init("test_task")
    await message_queue.push_output(mock_task, EventType.TEXT_ADD, {})
    
    message_str = await message_queue._queue.get()
    message = json.loads(message_str)
    
    assert message["flow"]["appId"] == "app_id"
    assert message["flow"]["stepStatus"] == "running"


@pytest.mark.asyncio
async def test_get_generator(message_queue):
    """测试消息生成器"""
    await message_queue.init("test_task")
    test_messages = ["msg1", "msg2", "msg3"]
    for msg in test_messages:
        await message_queue._queue.put(msg)
    
    messages = []
    async for msg in message_queue.get():
        messages.append(msg)
        if len(messages) == len(test_messages):
            await message_queue.close()
    
    assert messages == test_messages


@pytest.mark.asyncio
async def test_heartbeat(message_queue):
    """测试心跳消息"""
    await message_queue.init("test_task")
    await asyncio.sleep(3.5)  # 等待心跳触发
    
    # 检查队列中是否有心跳消息
    heartbeat_msg = await message_queue._queue.get()
    heartbeat_data = json.loads(heartbeat_msg)
    assert heartbeat_data["event"] == "heartbeat"
    
    await message_queue.close()


@pytest.mark.asyncio
async def test_close(message_queue):
    """测试关闭队列"""
    await message_queue.init("test_task")
    await message_queue.close()
    assert message_queue._close
    assert message_queue._heartbeat_task.cancelled()