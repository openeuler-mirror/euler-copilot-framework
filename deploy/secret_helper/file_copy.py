"""Copy files and directories

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import os
from pathlib import Path
from typing import Any


def chown_chmod(path: Path, mode_number: int, uid: int, gid: int) -> None:
    """Change ownership and permissions"""
    os.chown(str(path), uid, gid)     # type: ignore[]
    path.chmod(mode_number)

    for file in path.rglob("*"):
        os.chown(str(file), uid, gid)     # type: ignore[]
        file.chmod(mode_number)

def copy_file(file: Path, out_path: Path, secrets: dict[str, str]) -> None:
    print(f"copying: {file} to {out_path}")
    with file.open("r", encoding="utf-8") as f:
        data = f.read()
    if secrets:
        for key, value in secrets.items():
            data = data.replace(r"${" + key + "}", value)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(data)

def copy_single_item(from_path: Path, to_path: Path, secrets: dict[str, str]) -> None:
    """Copy a single file"""
    if from_path.is_file():
        print(f"found: {from_path}")
        copy_file(from_path, to_path, secrets)

    for file in from_path.rglob("*"):
        print(f"found: {file}")
        if any(p for p in file.parts if p.startswith(".")):
            print(f"skipping: {file}")
            continue
        out_path = to_path / file.relative_to(from_path)
        if file.is_file():
            copy_file(file, out_path, secrets)
        else:
            out_path.mkdir(parents=True, exist_ok=True)


def copy(from_path_str: str, to_path_str: str, mode: dict[str, Any]) -> None:
    """Copy files and directories"""
    # 校验Secrets是否存在
    secrets_path = Path("/secrets")
    if not secrets_path.exists():
        secrets = {}
    else:
        # 读取secrets
        secrets = {}
        for secret in secrets_path.iterdir():
            with secret.open("r") as f:
                secrets[secret.name] = f.read()

    # 检查文件位置
    from_path = Path(from_path_str)
    to_path = Path(to_path_str)

    # 检查文件是否存在
    if not from_path.exists():
        raise FileNotFoundError

    # 递归复制文件
    copy_single_item(from_path, to_path, secrets)

    # 设置权限
    mode_number = int(mode["mode"], 8)
    chown_chmod(to_path, mode_number, mode["uid"], mode["gid"])
