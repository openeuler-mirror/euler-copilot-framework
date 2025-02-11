"""Secret Injector

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path

import yaml

from file_copy import copy
from job import job

if __name__ == "__main__":
    config = Path("config.yaml")
    if not config.exists():
        job()

    else:
        with config.open("r") as f:
            config = yaml.safe_load(f)

        for copy_config in config["copy"]:
            copy(copy_config["from"], copy_config["to"], copy_config["mode"])
