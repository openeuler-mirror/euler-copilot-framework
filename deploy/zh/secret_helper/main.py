"""
注入Secret

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml
from file_copy import copy
from job import job

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--job", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if args.job:
        job()
        sys.exit(0)

    if args.copy:
        with Path(args.config).open("r") as f:
            config = yaml.safe_load(f)

        for copy_config in config["copy"]:
            secrets = copy_config.get("secrets", [])
            copy(copy_config["from"], copy_config["to"], copy_config["mode"], secrets)

        sys.exit(0)

    logger.error("Invalid argument")
