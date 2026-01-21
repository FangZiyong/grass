"""
StorageClient：统一的文件存储接口（本地文件系统/S3 兼容）
"""

import os
import posixpath
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional
from urllib.parse import urljoin

from django.conf import settings

from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


class StorageError(GrassAPIException):
    """存储操作异常"""

    default_detail = "Storage operation failed"
    default_code = ErrorCode.INTERNAL_ERROR
    status_code = 500


class StorageClient(ABC):
    """
    存储客户端抽象基类
    提供统一的文件上传/下载 URL 生成能力
    """

    @abstractmethod
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        上传字节数据到存储

        Args:
            key: 存储键（文件路径）
            data: 字节数据
            content_type: 内容类型（MIME type）

        Returns:
            file_url: 文件的访问 URL

        Raises:
            StorageError: 存储操作失败
        """
        pass

    @abstractmethod
    def put_file(
        self,
        key: str,
        file_path: str | Path,
        content_type: Optional[str] = None,
    ) -> str:
        """
        上传文件到存储

        Args:
            key: 存储键（文件路径）
            file_path: 本地文件路径
            content_type: 内容类型（MIME type）

        Returns:
            file_url: 文件的访问 URL

        Raises:
            StorageError: 存储操作失败
        """
        pass

    @abstractmethod
    def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        获取预签名 URL（用于临时访问）

        Args:
            key: 存储键（文件路径）
            expires_in: 过期时间（秒）

        Returns:
            presigned_url: 预签名 URL

        Raises:
            StorageError: 存储操作失败
        """
        pass


class LocalStorageClient(StorageClient):
    """
    本地文件系统存储客户端
    用于测试/开发环境
    """

    def __init__(
        self,
        base_dir: str | Path,
        base_url: str = "/storage/",
    ):
        """
        初始化本地存储客户端

        Args:
            base_dir: 本地存储根目录
            base_url: 文件访问的基础 URL（用于生成 file_url）
        """
        self.base_dir = Path(base_dir).resolve()
        self.base_url = base_url.rstrip("/") + "/"

        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_key(self, key: str) -> Path:
        """
        验证并规范化存储键，防止路径穿越攻击

        Args:
            key: 存储键

        Returns:
            规范化后的文件路径

        Raises:
            StorageError: 键无效或存在安全风险
        """
        if not key or key.strip() != key:
            raise StorageError(
                detail="Storage key cannot be empty or contain leading/trailing whitespace",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

        # 规范化路径，移除多余的斜杠和点
        normalized = posixpath.normpath(key.lstrip("/"))
        if normalized.startswith("..") or "/../" in normalized:
            raise StorageError(
                detail="Storage key contains path traversal (..)",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

        # 构建完整路径
        full_path = self.base_dir / normalized

        # 确保路径在基础目录内（防止路径穿越）
        try:
            full_path.resolve().relative_to(self.base_dir.resolve())
        except ValueError:
            raise StorageError(
                detail="Storage key resolves outside base directory",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

        return full_path

    def _validate_content_type(self, content_type: Optional[str]) -> None:
        """
        验证内容类型（可选，用于安全校验）

        Args:
            content_type: 内容类型

        Raises:
            StorageError: 内容类型无效
        """
        if content_type is None:
            return

        # 基本格式校验：MIME type 格式
        if not isinstance(content_type, str):
            raise StorageError(
                detail="Content type must be a string",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

        # 检查是否包含危险字符
        if ";" in content_type or "\n" in content_type or "\r" in content_type:
            raise StorageError(
                detail="Content type contains invalid characters",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """上传字节数据到本地存储"""
        self._validate_content_type(content_type)
        file_path = self._validate_key(key)

        try:
            # 确保父目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            file_path.write_bytes(data)

            # 生成访问 URL
            normalized_key = posixpath.normpath(key.lstrip("/"))
            file_url = urljoin(self.base_url, normalized_key)

            return file_url
        except OSError as e:
            raise StorageError(
                detail=f"Failed to write file: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=500,
            ) from e

    def put_file(
        self,
        key: str,
        file_path: str | Path,
        content_type: Optional[str] = None,
    ) -> str:
        """上传文件到本地存储"""
        self._validate_content_type(content_type)
        source_path = Path(file_path)

        if not source_path.exists():
            raise StorageError(
                detail=f"Source file does not exist: {file_path}",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        if not source_path.is_file():
            raise StorageError(
                detail=f"Source path is not a file: {file_path}",
                code=ErrorCode.BAD_REQUEST,
                status_code=400,
            )

        try:
            # 读取源文件内容
            data = source_path.read_bytes()

            # 使用 put_bytes 上传
            return self.put_bytes(key, data, content_type)
        except OSError as e:
            raise StorageError(
                detail=f"Failed to read source file: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=500,
            ) from e

    def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        获取预签名 URL（本地模式下直接返回 file_url）
        本地存储不需要签名，直接返回访问 URL
        """
        normalized_key = posixpath.normpath(key.lstrip("/"))
        file_url = urljoin(self.base_url, normalized_key)
        return file_url


class S3StorageClient(StorageClient):
    """
    S3 兼容存储客户端
    预留接口，可先 mock 实现
    """

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "us-east-1",
    ):
        """
        初始化 S3 存储客户端

        Args:
            endpoint_url: S3 服务端点 URL
            bucket_name: 存储桶名称
            access_key_id: 访问密钥 ID
            secret_access_key: 密钥
            region: 区域
        """
        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region

        # TODO: 初始化 boto3 client（可选，当前可 mock）
        # import boto3
        # self.client = boto3.client(
        #     's3',
        #     endpoint_url=endpoint_url,
        #     aws_access_key_id=access_key_id,
        #     aws_secret_access_key=secret_access_key,
        #     region_name=region,
        # )

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        上传字节数据到 S3（当前为 mock 实现）

        TODO: 实现真实的 S3 上传逻辑
        """
        # Mock 实现：返回一个占位 URL
        file_url = f"{self.endpoint_url}/{self.bucket_name}/{key}"
        return file_url

    def put_file(
        self,
        key: str,
        file_path: str | Path,
        content_type: Optional[str] = None,
    ) -> str:
        """
        上传文件到 S3（当前为 mock 实现）

        TODO: 实现真实的 S3 上传逻辑
        """
        source_path = Path(file_path)
        if not source_path.exists():
            raise StorageError(
                detail=f"Source file does not exist: {file_path}",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )

        # Mock 实现：读取文件并使用 put_bytes
        data = source_path.read_bytes()
        return self.put_bytes(key, data, content_type)

    def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        获取 S3 预签名 URL（当前为 mock 实现）

        TODO: 实现真实的 S3 presigned URL 生成
        """
        # Mock 实现：返回一个占位 URL
        presigned_url = f"{self.endpoint_url}/{self.bucket_name}/{key}?expires={expires_in}"
        return presigned_url


def get_storage_client() -> StorageClient:
    """
    根据配置获取存储客户端实例

    Returns:
        StorageClient: 存储客户端实例

    Raises:
        StorageError: 配置无效或客户端初始化失败
    """
    storage_type = getattr(settings, "STORAGE_TYPE", "LOCAL").upper()

    if storage_type == "LOCAL":
        base_dir = getattr(settings, "STORAGE_LOCAL_BASE_DIR", None)
        if not base_dir:
            # 默认使用项目根目录下的 storage 目录
            base_dir = Path(settings.BASE_DIR).parent / "storage"
        base_url = getattr(settings, "STORAGE_LOCAL_BASE_URL", "/storage/")
        return LocalStorageClient(base_dir=base_dir, base_url=base_url)

    elif storage_type == "S3":
        endpoint_url = getattr(settings, "STORAGE_S3_ENDPOINT_URL", "")
        bucket_name = getattr(settings, "STORAGE_S3_BUCKET_NAME", "")
        access_key_id = getattr(settings, "STORAGE_S3_ACCESS_KEY_ID", "")
        secret_access_key = getattr(settings, "STORAGE_S3_SECRET_ACCESS_KEY", "")

        if not all([endpoint_url, bucket_name, access_key_id, secret_access_key]):
            raise StorageError(
                detail="S3 storage configuration is incomplete",
                code=ErrorCode.BAD_REQUEST,
                status_code=500,
            )

        region = getattr(settings, "STORAGE_S3_REGION", "us-east-1")
        return S3StorageClient(
            endpoint_url=endpoint_url,
            bucket_name=bucket_name,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region=region,
        )

    else:
        raise StorageError(
            detail=f"Unsupported storage type: {storage_type}",
            code=ErrorCode.BAD_REQUEST,
            status_code=500,
        )

