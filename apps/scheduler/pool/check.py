"""文件检查器；检查文件是否存在、Hash是否发生变化；生成更新列表和删除列表

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from hashlib import sha256
from pathlib import Path

from apps.common.config import config
from apps.constants import APP_DIR, LOGGER, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.models.mongo import MongoDB


class FileChecker:
    """文件检查器"""

    def __init__(self) -> None:
        """初始化文件检查器"""
        self._hashes = {}
        self._dir_path = Path(config["SEMANTICS_DIR"])


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
                self._hashes[str(file.relative_to(self._dir_path))] = sha256(file.read_bytes()).hexdigest()
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
            if not (self._dir_path / list_item["_id"]).exists():
                deleted_list.append(list_item["_id"])
                continue
            # 判断是否发生变化
            if "hashes" not in list_item or self.diff_one(self._dir_path / list_item["_id"], list_item["hashes"]):
                changed_list.append(list_item["_id"])

        # 遍历目录
        for service_folder in self._dir_path.iterdir():
            # 判断是否新增？
            if service_folder.name not in items:
                changed_list += [service_folder.name]

        return changed_list, deleted_list
