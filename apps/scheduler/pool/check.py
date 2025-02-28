"""文件检查器；检查文件是否存在、Hash是否发生变化；生成更新列表和删除列表

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from hashlib import sha256
from typing import Optional

from anyio import Path

from apps.common.config import config
from apps.constants import APP_DIR, LOGGER, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.models.mongo import MongoDB


class FileChecker:
    """文件检查器"""

    def __init__(self) -> None:
        """初始化文件检查器"""
        self.hashes = {}
        self._dir_path = Path(config["SEMANTICS_DIR"])

    async def check_one(self, path: Path) -> dict[str, str]:
        """检查单个App/Service文件是否有变动"""
        hashes = {}
        if not await path.exists():
            err = FileNotFoundError(f"File {path} not found")
            raise err
        if not await path.is_dir():
            err = NotADirectoryError(f"Path {path} is not a directory")
            raise err

        async for file in path.iterdir():
            if await file.is_file():
                relative_path = file.relative_to(self._resource_path)
                hashes[relative_path.as_posix()] = sha256(await file.read_bytes()).hexdigest()
            elif await file.is_dir():
                hashes.update(await self.check_one(file))

        return hashes


    async def diff_one(self, path: Path, previous_hashes: Optional[dict[str, str]] = None) -> bool:
        """检查文件是否发生变化"""
        self._resource_path = path
        path_diff = self._resource_path.relative_to(config["SEMANTICS_DIR"])
        self.hashes[path_diff.as_posix()] = await self.check_one(path)
        return self.hashes[path_diff.as_posix()] != previous_hashes


    async def diff(self, check_type: MetadataType) -> tuple[list[str], list[str]]:
        """生成更新列表和删除列表"""
        if check_type == MetadataType.APP:
            collection = MongoDB.get_collection("app")
            self._dir_path = Path(config["SEMANTICS_DIR"]) / APP_DIR
        elif check_type == MetadataType.SERVICE:
            collection = MongoDB.get_collection("service")
            self._dir_path = Path(config["SEMANTICS_DIR"]) / SERVICE_DIR

        changed_list = []
        deleted_list = []

        # 查询所有条目
        try:
            items = await collection.find({}).to_list(None)
        except Exception as e:
            err = f"{check_type}类型数据的条目为空： {e!s}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        # 遍历列表
        for list_item in items:
            # 判断是否存在？
            if not await Path(self._dir_path / list_item["_id"]).exists():
                deleted_list.append(list_item["_id"])
                continue
            # 判断是否发生变化
            if await self.diff_one(Path(self._dir_path / list_item["_id"]), list_item.get("hashes", None)):
                changed_list.append(list_item["_id"])

        # 遍历目录
        item_names = [item["_id"] for item in items]
        async for service_folder in self._dir_path.iterdir():
            # 判断是否新增？
            if (
                service_folder.name not in item_names
                and service_folder.name not in deleted_list
                and service_folder.name not in changed_list
            ):
                changed_list += [service_folder.name]
                # 触发一次hash计算
                await self.diff_one(service_folder)

        return changed_list, deleted_list
