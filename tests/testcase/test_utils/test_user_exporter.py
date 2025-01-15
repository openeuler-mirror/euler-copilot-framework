# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
import os
import shutil
from unittest.mock import patch, mock_open, MagicMock
from apps.utils.user_exporter import UserExporter


class TestUserExporter(unittest.TestCase):

    def setUp(self):
        self.user_sub = "test_user_sub"

    @patch('apps.utils.user_exporter.UserManager.get_userinfo_by_user_sub')
    @patch('apps.utils.user_exporter.UserQaRecordManager.get_user_qa_record_by_user_sub')
    @patch('apps.utils.user_exporter.QaManager.query_encrypted_qa_pair_by_sessionid')
    def test_export_user_data(self, mock_query_encrypted_qa_pair, mock_get_user_qa_record, mock_get_userinfo):
        mock_get_userinfo.return_value = MagicMock()
        mock_get_user_qa_record.return_value = [MagicMock()]
        mock_query_encrypted_qa_pair.return_value = [MagicMock(), MagicMock()]
        zip_file_path = UserExporter.export_user_data(self.user_sub)
        assert os.path.exists(zip_file_path)
        os.remove(zip_file_path)

    @patch('apps.utils.user_exporter.UserManager.get_userinfo_by_user_sub')
    def test_export_user_info_to_xlsx(self, mock_get_userinfo):
        mock_get_userinfo.return_value = MagicMock()
        tmp_out_dir = './temp_dir'
        if not os.path.exists(tmp_out_dir):
            os.mkdir(tmp_out_dir)
        xlsx_file_path = os.path.join(tmp_out_dir, 'user_info_' + self.user_sub + '.xlsx')
        UserExporter.export_user_info_to_xlsx(tmp_out_dir, self.user_sub)
        assert os.path.exists(xlsx_file_path)
        os.remove(xlsx_file_path)
        os.rmdir(tmp_out_dir)

    @patch('apps.utils.user_exporter.UserQaRecordManager.get_user_qa_record_by_user_sub')
    @patch('apps.utils.user_exporter.QaManager.query_encrypted_qa_pair_by_sessionid')
    def test_export_chats_to_xlsx(self, mock_query_encrypted_qa_pair, mock_get_user_qa_record):
        mock_get_user_qa_record.return_value = [MagicMock()]
        mock_query_encrypted_qa_pair.return_value = [MagicMock(), MagicMock()]
        tmp_out_dir = './temp_dir'
        if not os.path.exists(tmp_out_dir):
            os.mkdir(tmp_out_dir)
        xlsx_file_path = os.path.join(tmp_out_dir, 'chat_title_2024-02-27 12:00:00.xlsx')
        UserExporter.export_chats_to_xlsx(tmp_out_dir, self.user_sub)
        assert os.path.exists(xlsx_file_path)
        os.remove(xlsx_file_path)
        os.rmdir(tmp_out_dir)


if __name__ == '__main__':
    unittest.main()
