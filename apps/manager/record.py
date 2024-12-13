# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import json
import logging
from typing import Literal

from sqlalchemy import desc, func, asc

from apps.common.security import Security
from apps.entities.response_data import RecordQueryData
from apps.models.mysql import Comment, MysqlDB, Record


class RecordManager:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def insert_encrypted_data(conversation_id, record_id, group_id, user_sub, question, answer):
        try:
            encrypted_question, question_encryption_config = Security.encrypt(
                question)
        except Exception as e:
            RecordManager.logger.info(f"Encryption failed: {e}")
            return
        try:
            encrypted_answer, answer_encryption_config = Security.encrypt(
                answer)
        except Exception as e:
            RecordManager.logger.info(f"Encryption failed: {e}")
            return

        question_encryption_config = json.dumps(question_encryption_config)
        answer_encryption_config = json.dumps(answer_encryption_config)

        new_qa_record = Record(conversation_id=conversation_id,
                               record_id=record_id,
                               encrypted_question=encrypted_question,
                               question_encryption_config=question_encryption_config,
                               encrypted_answer=encrypted_answer,
                               answer_encryption_config=answer_encryption_config,
                               group_id=group_id)
        try:
            with MysqlDB().get_session()as session:
                session.add(new_qa_record)
                session.commit()
            RecordManager.logger.info(
                f"Inserted encrypted data succeeded: {user_sub}")
        except Exception as e:
            RecordManager.logger.info(
                f"Insert encrypted data failed: {e}")
        del question_encryption_config
        del answer_encryption_config

    @staticmethod
    def query_encrypted_data_by_conversation_id(conversation_id, total_pairs=None, group_id=None, order: Literal["desc", "asc"] = "desc"):
        if order == "desc":
            order_func = desc
        else:
            order_func = asc

        results = []
        try:
            with MysqlDB().get_session() as session:
                subquery = session.query(
                    Record,
                    Comment.is_like,
                    func.row_number().over(
                        partition_by=Record.group_id,
                        order_by=order_func(Record.created_time)
                    ).label("rn")
                ).join(
                    Comment, Record.record_id == Comment.record_id, isouter=True
                ).filter(
                    Record.conversation_id == conversation_id
                ).subquery()

                if group_id is not None:
                    query = session.query(subquery).filter(
                        subquery.c.group_id != group_id, subquery.c.rn == 1).order_by(
                        order_func(subquery.c.created_time))
                else:
                    query = session.query(subquery).filter(subquery.c.rn == 1).order_by(order_func(subquery.c.created_time))

                if total_pairs is not None:
                    query = query.limit(total_pairs)
                else:
                    query = query

                query_results = query.all()
                for re in query_results:
                    res = RecordQueryData(
                        conversation_id=re.conversation_id, record_id=re.record_id,
                        encrypted_answer=re.encrypted_answer, encrypted_question=re.encrypted_question,
                        created_time=str(re.created_time),
                        is_like=re.is_like, group_id=re.group_id, question_encryption_config=json.loads(
                            re.question_encryption_config),
                        answer_encryption_config=json.loads(re.answer_encryption_config))
                    results.append(res)
        except Exception as e:
            RecordManager.logger.info(
                f"Query encrypted data by conversation_id failed: {e}")

        return results

    @staticmethod
    def query_encrypted_data_by_record_id(record_id):
        try:
            with MysqlDB().get_session() as session:
                result = session.query(Record).filter(
                    Record.record_id == record_id).first()
                return result
        except Exception as e:
            RecordManager.logger.info(
                f"query encrypted data by record_id failed: {e}")

    @staticmethod
    def delete_encrypted_qa_pair_by_conversation_id(conversation_id):
        try:
            with MysqlDB().get_session() as session:
                session.query(Record) \
                    .filter(Record.conversation_id == conversation_id) \
                    .delete()
                session.commit()
        except Exception as e:
            RecordManager.logger.info(
                f"Query encrypted data by conversation_id failed: {e}")
