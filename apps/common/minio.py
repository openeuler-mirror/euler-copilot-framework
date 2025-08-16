# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MinIO客户端"""

from typing import Any

import minio

from apps.common.config import Config


class MinioClient:
    """MinIO客户端"""

    client = minio.Minio(
        endpoint=Config().get_config().minio.endpoint,
        access_key=Config().get_config().minio.access_key,
        secret_key=Config().get_config().minio.secret_key,
        secure=Config().get_config().minio.secure,
    )

    @classmethod
    def check_bucket(cls, bucket_name: str) -> None:
        """检查Bucket是否存在"""
        if not cls.client.bucket_exists(bucket_name):
            cls.client.make_bucket(bucket_name)

    @classmethod
    def upload_file(cls, **kwargs: Any) -> None:
        """上传文件"""
        cls.client.put_object(**kwargs)

    @classmethod
    def download_file(cls, bucket_name: str, file_path: str) -> tuple[dict[str, Any], bytes]:
        """下载文件"""
        response = None
        try:
            obj_stat = cls.client.stat_object(bucket_name, file_path)
            metadata = obj_stat.metadata if isinstance(obj_stat.metadata, dict) else {}
            response = cls.client.get_object(bucket_name, file_path)
            doc = response.read()

            return metadata, doc
        finally:
            if response:
                response.close()
                response.release_conn()

    @classmethod
    def delete_file(cls, bucket_name: str, file_name: str) -> None:
        """删除文件"""
        cls.client.remove_object(bucket_name, file_name)
