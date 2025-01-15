# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from apps.cron.delete_user import DeleteUserCorn


class TestSchedulerJob(unittest.TestCase):

    @patch('apps.cron.scheduler_job.UserManager.query_userinfo_by_login_time')
    @patch('apps.cron.scheduler_job.UserQaRecordManager.get_user_qa_record_by_user_sub')
    @patch('apps.cron.scheduler_job.QaManager.delete_encrypted_qa_pair_by_sessionid')
    @patch('apps.cron.scheduler_job.CommentManager.delete_comment_by_user_sub')
    @patch('apps.cron.scheduler_job.UserManager.delete_userinfo_by_user_sub')
    def test_delete_user_success(self, mock_delete_userinfo_by_user_sub, mock_delete_comment_by_user_sub,
                                 mock_delete_encrypted_qa_pair_by_sessionid, mock_get_user_qa_record_by_user_sub,
                                 mock_query_userinfo_by_login_time):
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        userinfos = [MagicMock()]
        mock_query_userinfo_by_login_time.return_value = userinfos
        mock_get_user_qa_record_by_user_sub.return_value = [MagicMock()]
        DeleteUserCorn.delete_user()
        assert mock_query_userinfo_by_login_time.called
        assert mock_get_user_qa_record_by_user_sub.called
        assert mock_delete_encrypted_qa_pair_by_sessionid.called
        assert mock_delete_comment_by_user_sub.called
        assert mock_delete_userinfo_by_user_sub.called

    @patch('apps.cron.scheduler_job.UserManager.query_userinfo_by_login_time')
    def test_delete_user_exception(self, mock_query_userinfo_by_login_time):
        mock_query_userinfo_by_login_time.side_effect = Exception("An error occurred")
        DeleteUserCorn.delete_user()
        assert mock_query_userinfo_by_login_time.called
        assert DeleteUserCorn.logger.info.called


if __name__ == '__main__':
    unittest.main()
