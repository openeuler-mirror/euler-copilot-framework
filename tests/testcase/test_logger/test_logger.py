# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import unittest
import logging
import os
from apps.logger import SizedTimedRotatingFileHandler, get_logger


class TestSizedTimedRotatingFileHandler(unittest.TestCase):

    def test_should_rollover_max_bytes(self):
        max_bytes = 100
        handler = SizedTimedRotatingFileHandler("test.log", max_bytes=max_bytes)
        # Assume the file size exceeds max_bytes
        self.assertTrue(handler.shouldRollover(logging.makeLogRecord({"msg": "test log"})))

    def test_should_rollover_time(self):
        handler = SizedTimedRotatingFileHandler("test.log", when="S", interval=1, backup_count=0)
        # Assume the current time is greater than the next rollover time
        handler.rolloverAt = 0
        self.assertTrue(handler.shouldRollover(logging.makeLogRecord({"msg": "test log"})))


class TestGetLogger(unittest.TestCase):

    def test_get_logger_dev_env(self):
        os.environ["ENV"] = "dev"
        logger = get_logger()
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)

    def test_get_logger_prod_env(self):
        os.environ["ENV"] = "prod"
        logger = get_logger()
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], SizedTimedRotatingFileHandler)
        self.assertEqual(logger.handlers[0].max_bytes, 5000000)
        self.assertEqual(logger.handlers[0].backupCount, 30)


if __name__ == '__main__':
    unittest.main()
