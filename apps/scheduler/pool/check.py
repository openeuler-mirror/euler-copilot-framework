"""文件检查器；检查文件是否存在、Hash是否发生变化；生成更新列表和删除列表

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path

from apps.common.config import config
from apps.entities.enum_var import MetadataType
from apps.models.mongo import MongoDB
from apps.scheduler.pool.util import get_long_hash


class FileChecker:
    """文件检查器"""

    def __init__(self) -> None:
        """初始化文件检查器"""
        self._hashes = {}
        self._dir_path = Path(config["SERVICE_DIR"])


    def check_one(self, path: Path) -> None:
        """检查单个App/Service文件是否有变动"""
        if not path.exists():
            err = FileNotFoundError(f"File {path} not found")
            raise err
        if path.is_file():
            err = NotADirectoryError(f"File {path} is not a directory")
            raise err

        for file in path.iterdir():
            if file.is_file():
                self._hashes[str(file.relative_to(self._dir_path))] = get_long_hash(file.read_bytes())
            elif file.is_dir():
                self.check_one(file)


    def diff_one(self, path: Path, previous_hashes: dict[str, str]) -> bool:
        """检查文件是否发生变化"""
        self._hashes = {}
        self.check_one(path)
        return self._hashes != previous_hashes


    async def diff(self, check_type: MetadataType) -> tuple[list[str], list[str]]:
        """生成更新列表和删除列表"""
        if check_type == MetadataType.APP:
            collection = MongoDB.get_collection("app")
            self._dir_path = Path(config["SERVICE_DIR"]) / "app"
        elif check_type == MetadataType.SERVICE:
            collection = MongoDB.get_collection("service")
            self._dir_path = Path(config["SERVICE_DIR"]) / "service"

        changed_list = []
        deleted_list = []

        try:
            # 查询所有条目
            cursor = collection.find({})
            async for item in cursor:
                hashes = item.get("hashes", {})
                # 判断是否存在？
                if not (self._dir_path / item.get("name")).exists():
                    deleted_list.append(item.get("name"))
                    continue
                # 判断是否发生变化
                if self.diff_one(self._dir_path / item.get("name"), hashes):
                    changed_list.append(item.get("name"))

        except Exception as e:
            err = f"Failed to check {check_type} files: {e!s}"
            raise RuntimeError(err) from e

        return changed_list, deleted_list
