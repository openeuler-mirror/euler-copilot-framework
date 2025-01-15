# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest

from apps.constants import *


class TestCurrentRevisionVersion(unittest.TestCase):

    def test_current_revision_version(self):
        self.assertEqual(CURRENT_REVISION_VERSION, '0.0.0')

    def test_new_chat(self):
        self.assertEqual(NEW_CHAT, 'New Chat')


if __name__ == '__main__':
    unittest.main()
