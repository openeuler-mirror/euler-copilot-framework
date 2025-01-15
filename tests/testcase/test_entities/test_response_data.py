# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from datetime import datetime
from apps.entities.response_data import *


class TestResponseData(unittest.TestCase):
    def test_valid_response_data(self):
        data = {
            "code": 200,
            "message": "Success",
            "result": {"key": "value"}
        }
        response_data = ResponseData.model_validate(data)
        self.assertEqual(response_data.model_dump(), data)

    def test_invalid_response_data(self):
        data = {
            "code": "200",
            "message": "Success",
            "result": []
        }
        self.assertRaises(Exception, ResponseData.model_validate, data)


class TestSessionData(unittest.TestCase):
    def test_valid_session_data(self):
        data = {
            "session_id": "session123",
            "title": "Session Title",
            "created_time": datetime.utcnow()
        }
        session_data = ConversationData.model_validate(data)
        self.assertEqual(session_data.model_dump(), data)

    def test_invalid_session_data(self):
        data = {
            "session_id": 111222,
            "title": "Session Title",
            "created_time": datetime.utcnow()
        }
        self.assertRaises(Exception, ConversationData.model_validate, data)


class TestSessionListData(unittest.TestCase):

    def test_valid_session_list_data(self):
        data = {
            "code": 200,
            "message": "Success",
            "result": [{"session_id": "session123", "title": "Session Title", "created_time": datetime.utcnow()}]
        }
        session_list_data = ConversationListData.model_validate(data)
        self.assertEqual(session_list_data.model_dump(), data)

    def test_invalid_session_list_data(self):
        data = {
            "code": 200,
            "message": "Success"
        }
        self.assertRaises(Exception, ConversationListData.model_validate, data)


class TestQaRecordData(unittest.TestCase):
    def test_valid_qa_record_data(self):
        data = {
            "session_id": "session123",
            "record_id": "record123",
            "question": "Test Question",
            "answer": "Test Answer",
            "is_like": 1,
            "created_time": datetime.utcnow(),
            "group_id": "group123"
        }
        qa_record_data = RecordData.model_validate(data)
        self.assertEqual(qa_record_data.model_dump(), data)

    def test_invalid_qa_record_data(self):
        data = {
            "session_id": "session123",
            "record_id": "record123",
            "is_like": 1,
            "created_time": datetime.utcnow(),
            "group_id": "group123"
        }
        self.assertRaises(Exception, RecordData.model_validate, data)


class TestQaRecordListData(unittest.TestCase):
    def test_valid_qa_record_list_data(self):
        data = {
            "code": 200,
            "message": "Success",
            "result": [{
                "session_id": "session123",
                "record_id": "record123",
                "question": "Test Question",
                "answer": "Test Answer",
                "is_like": 1,
                "created_time": datetime.utcnow(),
                "group_id": "group123"
            }]
        }
        qa_record_list_data = RecordListData.model_validate(data)
        self.assertEqual(qa_record_list_data.model_dump(), data)

    def test_invalid_qa_record_list_data(self):
        data = {
            "code": 200,
            "message": "Success"
        }
        self.assertRaises(Exception, RecordListData.model_validate, data)


class TestIsAlive(unittest.TestCase):
    def test_valid_is_alive(self):
        data = {
            "code": 200,
            "message": "Success",
        }
        is_alive = IsAlive.model_validate(data)
        self.assertEqual(is_alive.model_dump(), data)

    def test_invalid_is_alive(self):
        data = {
            "code": "200",
            "message": None,
        }
        self.assertRaises(Exception, IsAlive.model_validate, data)


class TestQaRecordQueryData(unittest.TestCase):
    def test_valid_qa_record_query_data(self):
        data = {
            "user_qa_record_id": "record123",
            "qa_record_id": "record123",
            "encrypted_question": "Test Question",
            "question_encryption_config": {},
            "encrypted_answer": "Test Answer",
            "answer_encryption_config": {},
            "group_id": "group123",
            "is_like": 1,
            "created_time": "2024/07/16 18:13"
        }
        qa_record_query_data = RecordQueryData.model_validate(data)
        self.assertEqual(qa_record_query_data.model_dump(), data)

    def test_invalid_qa_record_query_data(self):
        data = {
            "user_qa_record_id": "record123",
            "qa_record_id": "record123",
            "group_id": "group123",
            "is_like": 1,
            "created_time": "2024/07/16 18:13"
        }
        self.assertRaises(Exception, RecordQueryData.model_validate, data)


class TestPluginData(unittest.TestCase):
    def test_valid_plugin_data(self):
        data = {
            "plugin_name": "gen_graph",
            "plugin_description": "绘图插件",
            "plugin_auth": None,
        }
        plugin_data = PluginData.model_validate(data)
        self.assertEqual(plugin_data.model_dump(), data)

    def test_invalid_plugin_data(self):
        data = {
            "plugin_name": "",
            "plugin_description": None
        }
        self.assertRaises(Exception, PluginData.model_validate, data)


class TestPluginListData(unittest.TestCase):
    def test_valid_plugin_list_data(self):
        data = {
            "code": 200,
            "message": "Success",
            "result": [{
                "plugin_name": "gen_graph",
                "plugin_description": "123",
                "plugin_auth": None,
            }]
        }
        plugin_list_data = PluginListData.model_validate(data)
        self.assertEqual(plugin_list_data.model_dump(), data)

    def test_invalid_plugin_list_data(self):
        data = {
            "code": 200,
            "message": "Success"
        }
        self.assertRaises(Exception, PluginListData.model_validate, data)


if __name__ == '__main__':
    unittest.main()
