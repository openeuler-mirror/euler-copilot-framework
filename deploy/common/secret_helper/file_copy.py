"""
Copy files and directories

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def chown_chmod(path: Path, mode_number: int, uid: int, gid: int) -> None:
    """改变文件权限"""
    os.chown(str(path), uid, gid)     # type: ignore[attr-defined]
    path.chmod(mode_number)

    for file in path.rglob("*"):
        os.chown(str(file), uid, gid)     # type: ignore[attr-defined]
        file.chmod(mode_number)

def copy_file(file: Path, out_path: Path, secrets: dict[str, str]) -> None:
    """复制单个文件"""
    logger.info("复制文件: %s to %s", file, out_path)
    with file.open("r", encoding="utf-8") as f:
        data = f.read()
    if secrets:
        for key, value in secrets.items():
            data = data.replace(r"${" + key + "}", value)
    # 确保父文件夹存在
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(data)

def process_item(from_path: Path, to_path: Path, secrets: dict[str, str]) -> None:
    """处理Config中的单个项"""
    if from_path.is_file():
        logger.info("找到文件: %s", from_path)
        copy_file(from_path, to_path, secrets)

    for file in from_path.rglob("*"):
        logger.info("找到文件: %s", file)
        if any(p for p in file.parts if p.startswith(".")):
            logger.info("跳过文件: %s", file)
            continue
        out_path = to_path / file.relative_to(from_path)
        if file.is_file():
            copy_file(file, out_path, secrets)
        else:
            out_path.mkdir(parents=True, exist_ok=True)


def copy(from_path_str: str, to_path_str: str, mode: dict[str, Any], secrets_dir: list[str]) -> None:
    """复制文件和目录"""
    # 校验Secrets是否存在
    secrets = {}
    for dir_name in secrets_dir:
        secrets_path = Path(dir_name)
        if not secrets_path.exists():
            continue
        if not secrets_path.is_dir():
            err = f"{dir_name} 不是文件夹"
            raise FileNotFoundError(err)

        # 读取secrets
        for secret in secrets_path.iterdir():
            if secret.name.startswith(".") or secret.name.startswith("_") or not secret.is_file():
                continue
            with secret.open("r") as f:
                secrets[secret.name] = f.read()

    # 检查文件位置
    from_path = Path(from_path_str)
    to_path = Path(to_path_str)

    # 检查文件是否存在
    if not from_path.exists():
        raise FileNotFoundError

    # 递归复制文件
    process_item(from_path, to_path, secrets)

    # 设置权限
    mode_number = int(mode["mode"], 8)
    chown_chmod(to_path, mode_number, mode["uid"], mode["gid"])
