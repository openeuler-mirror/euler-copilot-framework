"""MinIO客户端"""

from typing import Any

import minio

from apps.common.config import config


class MinioClient:
    """MinIO客户端"""

    client = minio.Minio(
        endpoint=config["MINIO_ENDPOINT"],
        access_key=config["MINIO_ACCESS_KEY"],
        secret_key=config["MINIO_SECRET_KEY"],
        secure=config["MINIO_SECURE"],
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
