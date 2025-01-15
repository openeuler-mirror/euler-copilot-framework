# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest

from apps.entities.request_data import *


class TestRequestData(unittest.TestCase):

    def test_valid_request_data(self):
        data = {
            "question": "Test question",
            "session_id": "session123",
            "qa_record_id": "qa123",
            "user_selected_descriptions": ["desc1", "desc2"]
        }
        request_data = RequestData(**data)
        self.assertEqual(request_data.dict(), data)

    def test_missing_optional_field(self):
        data = {
            "question": "Test question",
            "session_id": "session123",
        }
        request_data = RequestData(**data)
        self.assertIsNone(request_data.record_id)
        self.assertIsNone(request_data.user_selected_descriptions)

    def test_question_min_length(self):
        with self.assertRaises(ValueError):
            RequestData(question="", session_id="session123")

    def test_question_max_length(self):
        with self.assertRaises(ValueError):
            RequestData(question="x" * 4001, session_id="session123")

    def test_session_id_required(self):
        with self.assertRaises(ValueError):
            RequestData(question="Test question")

    def test_session_id_min_length(self):
        session_id = ""
        request_data = RequestData(question="Test question", session_id=session_id)
        self.assertEqual(request_data.conversation_id, "")

    def test_session_id_max_length(self):
        session_id = "x" * 129
        request_data = RequestData(question="Test question", session_id=session_id)
        self.assertEqual(len(request_data.conversation_id), 129)

    def test_qa_record_id_optional(self):
        request_data = RequestData(question="Test question", session_id="session123")
        self.assertIsNone(request_data.record_id)

    def test_user_selected_descriptions_optional(self):
        request_data = RequestData(question="Test question", session_id="session123")
        self.assertIsNone(request_data.user_selected_descriptions)


if __name__ == '__main__':
    unittest.main()
