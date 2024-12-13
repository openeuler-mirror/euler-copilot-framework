# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler

from apps.common.config import config


class SizedTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, max_bytes=0, backup_count=0, encoding=None,
                 delay=False, when='midnight', interval=1, utc=False):
        super().__init__(filename, when, interval, backup_count, encoding, delay, utc)
        self.max_bytes = max_bytes

    def shouldRollover(self, record):
        if self.stream is None:
            self.stream = self._open()
        if self.max_bytes > 0:
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)
            if self.stream.tell()+len(msg) >= self.max_bytes:
                return 1
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        return 0

    def doRollover(self):
        self.stream.close()
        os.chmod(self.baseFilename, 0o440)
        TimedRotatingFileHandler.doRollover(self)
        os.chmod(self.baseFilename, 0o640)

LOG_FORMAT = '[{asctime}][{levelname}][{name}][P{process}][T{thread}][{message}][{funcName}({filename}:{lineno})]'

if config["LOG"] == "stdout":
    handlers = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    }
else:
    LOG_DIR = './logs'
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, 0o750)
    handlers = {
        'default': {
            'formatter': 'default',
            'class': 'apps.logger.SizedTimedRotatingFileHandler',
            'filename': f"{LOG_DIR}/app.log",
            'backup_count': 30,
            'when': 'MIDNIGHT',
            'max_bytes': 5000000
        }
    }

log_config = {
    "version": 1,
    'disable_existing_loggers': False,
    "formatters": {
        "default": {
            '()': 'logging.Formatter',
            'fmt': LOG_FORMAT,
            'style': '{'
        }
    },
    "handlers": handlers,
    "loggers": {
        "uvicorn": {
            "level": "INFO",
            "handlers": ["default"],
            'propagate': False
        },
        "uvicorn.errors": {
            "level": "INFO",
            "handlers": ["default"],
            'propagate': False
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["default"],
            'propagate': False
        }
    }
}


def get_logger():
    logger = logging.getLogger('uvicorn')
    logger.setLevel(logging.INFO)
    if config['LOG'] != 'stdout':
        rotate_handler = SizedTimedRotatingFileHandler(
            filename=f'{LOG_DIR}/app.log', when='MIDNIGHT', backup_count=30, max_bytes=5000000)
        logger.addHandler(rotate_handler)
    logger.propagate = False
    return logger
