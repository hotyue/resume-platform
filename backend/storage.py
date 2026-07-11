"""
S3 存储层 — 支持群晖 NAS / 其他 S3 兼容服务
路径规则: deliveries/{年}/{月}/{日}/{order_no}_{filename}
"""
import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Optional

from config import settings


class StorageError(Exception):
    """存储操作异常"""
    pass


class S3Storage:
    """S3 兼容存储客户端"""

    def __init__(self):
        if not settings.s3_enabled:
            raise StorageError(
                "S3 存储未配置，请设置 S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY 环境变量"
            )

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},  # 群晖兼容
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    @staticmethod
    def build_key(order_no: str, filename: str) -> str:
        """生成存储路径: deliveries/YYYY/MM/DD/order_no_filename"""
        now = datetime.now()
        return f"deliveries/{now.year}/{now.month:02d}/{now.day:02d}/{order_no}_{filename}"

    def upload_file(self, key: str, data: bytes, content_type: str) -> dict:
        """
        上传文件到 S3
        :param key: 存储路径
        :param data: 文件字节内容
        :param content_type: MIME 类型
        :return: {"key": ..., "size": ..., "etag": ...}
        """
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            return {"key": key}
        except ClientError as e:
            raise StorageError(f"S3 上传失败: {e}")

    def get_presigned_url(self, key: str, expires: int = 172800) -> str:
        """
        生成预签名下载 URL
        :param key: 存储路径
        :param expires: 有效期（秒），默认 48 小时
        :return: 预签名 URL
        """
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except ClientError as e:
            raise StorageError(f"S3 生成下载链接失败: {e}")

    def delete_file(self, key: str) -> bool:
        """删除文件"""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            raise StorageError(f"S3 删除失败: {e}")

    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """
        列出文件（用于大数据分析）
        :param prefix: 前缀过滤，如 "deliveries/2026/07/"
        :param max_keys: 最大数量
        :return: [{"key": ..., "size": ..., "last_modified": ...}, ...]
        """
        try:
            resp = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=max_keys
            )
            return [
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
                for obj in resp.get("Contents", [])
                if obj["Key"] != prefix  # 排除文件夹占位符
            ]
        except ClientError as e:
            raise StorageError(f"S3 列出文件失败: {e}")


# 全局单例
_storage_instance: Optional[S3Storage] = None


def get_storage() -> S3Storage:
    """获取 S3 存储实例（单例）"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = S3Storage()
    return _storage_instance
