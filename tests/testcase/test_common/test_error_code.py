# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest

from apps.entities.error_code import *


class TestOIDCConstants(unittest.TestCase):
    def test_oidc_login_fail(self):
        self.assertEqual(OIDC_LOGIN_FAIL, 2001)

    def test_oidc_login_fail_msg(self):
        self.assertEqual(OIDC_LOGIN_FAIL_MSG, "oidc login fail")

    def test_oidc_logout(self):
        self.assertEqual(OIDC_LOGOUT, 460)

    def test_oidc_logout_msg(self):
        self.assertEqual(OIDC_LOGOUT_FAIL_MSG, "need logout oidc")

    def test_local_deploy_login_failed(self):
        self.assertEqual(LOCAL_DEPLOY_LOGIN_FAIL, 3001)

    def test_local_deploy_login_fail_msg(self):
        self.assertEqual(LOCAL_DEPLOY_FAIL_MSG, "wrong account or passwd")


if __name__ == "__main__":
    unittest.main()
