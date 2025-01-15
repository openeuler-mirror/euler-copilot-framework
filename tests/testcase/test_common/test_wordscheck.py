# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
from unittest.mock import patch, MagicMock
from apps.common.wordscheck import WordsCheck


class TestWordsCheck(unittest.TestCase):

    @patch('requests.post')
    def test_detect_ok_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "ok"}'
        mock_post.return_value = mock_response

        result = WordsCheck.detect("test content")

        self.assertTrue(result)

    @patch('requests.post')
    def test_detect_not_ok_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = WordsCheck.detect("test content")

        self.assertFalse(result)

    @patch('requests.post')
    def test_detect_not_ok_content(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"status": "not ok"}'
        mock_post.return_value = mock_response

        with patch.object(WordsCheck, 'detect', return_value=False):
            result = WordsCheck.detect("test content")

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
