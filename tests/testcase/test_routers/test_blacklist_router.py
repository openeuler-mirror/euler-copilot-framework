import unittest
from datetime import datetime, timezone
import pytz
from unittest.mock import patch
from unittest import TestCase

from fastapi.testclient import TestClient
from fastapi import status, FastAPI, Request

from apps.routers.blacklist import router
from apps.dependency import verify_csrf_token, get_current_user
from apps.entities.user import User


def mock_csrf_token(request: Request):
    return


def mock_get_user(request: Request):
    return User(user_sub="1", organization="openEuler")


class TestBlacklistRouter(TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[verify_csrf_token] = mock_csrf_token
        app.dependency_overrides[get_current_user] = mock_get_user
        cls.client = TestClient(app)

    @patch('apps.routers.blacklist.UserBlacklistManager.get_blacklisted_users')
    def test_get_blacklist_user_success(self, mock_get_blacklisted_users):
        mock_get_blacklisted_users.return_value = [
            {
                'user_id': 1,
                'organization': 'openEuler',
                'credit': 100,
                'login_time': datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
            }
        ]
        response = self.client.get('/blacklist/user')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.UserBlacklistManager.get_blacklisted_users')
    def test_get_blacklist_user_failed(self, mock_get_blacklisted_users):
        mock_get_blacklisted_users.return_value = None
        response = self.client.get('/blacklist/user')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)

    @patch('apps.routers.blacklist.QuestionBlacklistManager.get_blacklisted_questions')
    def test_get_blacklist_question_success(self, mock_get_blacklisted_questions):
        mock_get_blacklisted_questions.return_value = [
            {
                'id': 1,
                'question': 'Test question.',
                'answer': 'Test answer.',
                'reason': 'Test reason.',
                'created_time': datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
            }
        ]
        response = self.client.get('/blacklist/question')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.QuestionBlacklistManager.get_blacklisted_questions')
    def test_get_blacklist_question_failed(self, mock_get_blacklisted_questions):
        mock_get_blacklisted_questions.return_value = None
        response = self.client.get('/blacklist/question')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)

    @patch('apps.routers.blacklist.QuestionBlacklistManager.change_blacklisted_questions')
    def test_change_blacklist_question(self, mock_change_blacklist_questions):
        mock_change_blacklist_questions.return_value = True
        response = self.client.post('/blacklist/question', json={
            'question': 'Test question.',
            'answer': 'Test answer',
            'is_deletion': 0
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.UserBlacklistManager.change_blacklisted_users')
    def test_change_blacklist_user_success(self, mock_change_blacklist_users):
        mock_change_blacklist_users.return_value = True
        response = self.client.post('/blacklist/user', json={
            'user_sub': "1",
            'is_ban': 0
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.UserBlacklistManager.change_blacklisted_users')
    def test_change_blacklist_user_failed(self, mock_change_blacklist_users):
        mock_change_blacklist_users.return_value = None
        response = self.client.post('/blacklist/user', json={
            'user_sub': "1",
            'is_ban': 0
        })
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)

    @patch('apps.routers.blacklist.QuestionBlacklistManager.get_blacklisted_questions')
    def test_get_abuse_report_success(self, mock_get_abuse_report):
        mock_get_abuse_report.return_value = [
            {
                'id': 2,
                'question': 'Test Question',
                'answer': 'Test Answer',
                'reason': 'Test Reason',
                'created_time': datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
            }
        ]
        response = self.client.get('/blacklist/abuse')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.QuestionBlacklistManager.get_blacklisted_questions')
    def test_get_abuse_report_failed(self, mock_get_abuse_report):
        mock_get_abuse_report.return_value = None
        response = self.client.get('/blacklist/abuse')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)

    @patch('apps.routers.blacklist.AbuseManager.change_abuse_report')
    def test_abuse_report_success(self, mock_change_abuse_report):
        mock_change_abuse_report.return_value = True
        response = self.client.post('/blacklist/complaint', json={
            'user_sub': 1,
            'record_id': '012345',
            'reason': 'Test Reason'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.AbuseManager.change_abuse_report')
    def test_abuse_report_failed(self, mock_change_abuse_report):
        mock_change_abuse_report.return_value = None
        response = self.client.post('/blacklist/complaint', json={
            'record_id': '012345',
            'reason': 'Test Reason'
        })
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)

    @patch('apps.routers.blacklist.AbuseManager.audit_abuse_report')
    def test_change_abuse_report_success(self, mock_audit_abuse_report):
        mock_audit_abuse_report.return_value = True
        response = self.client.post('/blacklist/abuse', json={
            'id': 1,
            'is_deletion': True
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['result']), 1)

    @patch('apps.routers.blacklist.AbuseManager.audit_abuse_report')
    def test_change_abuse_report_failed(self, mock_audit_abuse_report):
        mock_audit_abuse_report.return_value = None
        response = self.client.post('/blacklist/abuse', json={
            'id': 1,
            'is_deletion': True
        })
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(len(response.json()['result']), 0)


if __name__ == '__main__':
    unittest.main()
