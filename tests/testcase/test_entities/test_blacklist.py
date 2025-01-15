import unittest

from apps.entities.blacklist import *


class TestQuestionBlacklistRequest(unittest.TestCase):
    def test_valid_question_blacklist_request(self):
        data = {
            "question": "1111",
            "answer": "2222",
            "is_deletion": 1
        }
        request = QuestionBlacklistRequest.model_validate(data)
        self.assertEqual(request.model_dump(), data)

    def test_invalid_question_blacklist_request(self):
        data = {
            "question": "1111",
            "answer": "2222"
        }
        self.assertRaises(Exception, QuestionBlacklistRequest.model_validate, data)


class TestUserBlacklistRequest(unittest.TestCase):
    def test_valid_user_blacklist_request(self):
        data = {
            "user_sub": "111",
            "is_ban": 1
        }
        request = UserBlacklistRequest.model_validate(data)
        self.assertEqual(request.model_dump(), data)

    def test_invalid_user_blacklist_request(self):
        data = {
            "is_ban": 1
        }
        self.assertRaises(Exception, UserBlacklistRequest.model_validate, data)


class TestAbuseRequest(unittest.TestCase):
    def test_valid_abuse_request(self):
        data = {
            "record_id": "record123",
            "reason": "测试原因"
        }
        request = AbuseRequest.model_validate(data)
        self.assertEqual(request.model_dump(), data)

    def test_invalid_abuse_request(self):
        data = {
            "record_id": "record123",
        }
        self.assertRaises(Exception, AbuseRequest.model_validate, data)


class TestAbuseProcessRequest(unittest.TestCase):
    def test_valid_abuse_process_request(self):
        data = {
            "id": 123,
            "is_deletion": 1
        }
        request = AbuseProcessRequest.model_validate(data)
        self.assertEqual(request.model_dump(), data)

    def test_invalid_process_request(self):
        data = {
            "id": 123,
        }
        self.assertRaises(Exception, AbuseProcessRequest.model_validate, data)


if __name__ == '__main__':
    unittest.main()