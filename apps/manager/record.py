"""问答对Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import traceback
import uuid
from typing import Literal, Optional

from apps.constants import LOGGER
from apps.entities.collection import (
    Record,
    RecordGroup,
)
from apps.models.mongo import MongoDB


class RecordManager:
    """问答对相关操作"""

    @staticmethod
    async def create_record_group(user_sub: str, conversation_id: str, task_id: str) -> Optional[str]:
        """创建问答组"""
        group_id = str(uuid.uuid4())
        record_group_collection = MongoDB.get_collection("record_group")
        conversation_collection = MongoDB.get_collection("conversation")
        record_group = RecordGroup(
            _id=group_id,
            user_sub=user_sub,
            conversation_id=conversation_id,
            task_id=task_id,
        )

        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                # RecordGroup里面加一条记录
                await record_group_collection.insert_one(record_group.model_dump(by_alias=True), session=session)
                # Conversation里面加一个ID
                await conversation_collection.update_one({"_id": conversation_id}, {"$push": {"record_groups": group_id}}, session=session)
        except Exception as e:
            LOGGER.info(f"Create record group failed: {e}")
            return None

        return group_id


    @staticmethod
    async def insert_record_data_into_record_group(user_sub: str, group_id: str, record: Record) -> Optional[str]:
        """加密问答对，并插入MongoDB中的特定问答组"""
        group_collection = MongoDB.get_collection("record_group")
        try:
            await group_collection.update_one(
                {"_id": group_id, "user_sub": user_sub},
                {"$push": {"records": record.model_dump(by_alias=True)}},
            )
            return record.record_id
        except Exception as e:
            LOGGER.info(f"Insert encrypted data failed: {e!s}\n{traceback.format_exc()}")
            return None

    @staticmethod
    async def query_record_by_conversation_id(
        user_sub: str, conversation_id: str, total_pairs: Optional[int] = None, order: Literal["desc", "asc"] = "desc",
    ) -> list[Record]:
        """查询ConversationID的最后n条问答对

        每个record_group只取最后一条record
        """
        sort_order = -1 if order == "desc" else 1

        record_group_collection = MongoDB.get_collection("record_group")
        try:
            # 得到conversation的全部record_group id
            record_groups = await record_group_collection.aggregate([
                {"$match": {"conversation_id": conversation_id, "user_sub": user_sub}},
                {"$sort": {"created_at": sort_order}},
                {"$project": {"_id": 1}},
                {"$limit": total_pairs} if total_pairs is not None else {},
            ])

            records = []
            async for record_group_id in record_groups:
                record = await record_group_collection.aggregate([
                    {"$match": {"_id": record_group_id["_id"]}},
                    {"$project": {"records": 1}},
                    {"$unwind": "$records"},
                    {"$sort": {"records.created_at": -1}},
                    {"$limit": 1},
                ])
                record = await record.to_list(length=1)
                if not record:
                    LOGGER.info(f"Record group {record_group_id} has no record.")
                    continue

                records.append(Record.model_validate(record[0]["records"]))
            return records
        except Exception as e:
            LOGGER.info(f"Query encrypted data by conversation_id failed: {e}")
            return []

    @staticmethod
    async def query_record_group_by_conversation_id(conversation_id: str, total_pairs: Optional[int] = None) -> list[RecordGroup]:
        """查询对话ID的最后n条问答组

        包含全部record_group及其关联的record
        """
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            pipeline = [
                {"$match": {"conversation_id": conversation_id}},
                {"$sort": {"created_at": -1}},
            ]
            if total_pairs is not None:
                pipeline.append({"$limit": total_pairs})

            records = await record_group_collection.aggregate(pipeline)
            return [RecordGroup.model_validate(record) async for record in records]
        except Exception as e:
            LOGGER.info(f"Query record group by conversation_id failed: {e}")
            return []

    @staticmethod
    async def verify_record_in_group(group_id: str, record_id: str, user_sub: str) -> bool:
        """验证记录是否在组中

        :param record_id: 记录ID，设置了则会去查询指定记录ID的记录
        :return: 记录是否存在
        """
        try:
            record_group_collection = MongoDB.get_collection("record_group")
            record_data = await record_group_collection.find_one({"_id": group_id, "user_sub": user_sub, "records._id": record_id})
            return bool(record_data)
        except Exception as e:
            LOGGER.info(f"Query encrypted data by group_id failed: {e}")
            return False

    @staticmethod
    async def check_group_id(group_id: str, user_sub: str) -> bool:
        """检查group_id是否存在"""
        record_group_collection = MongoDB.get_collection("record_group")
        try:
            result = await record_group_collection.find_one({"_id": group_id, "user_sub": user_sub})
            return bool(result)
        except Exception as e:
            LOGGER.info(f"Group_id {group_id} not found: {e}")
            return False
