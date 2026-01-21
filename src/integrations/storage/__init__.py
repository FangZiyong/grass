"""
存储集成模块：提供统一的文件上传/下载 URL 生成能力
"""

from integrations.storage.client import StorageClient, get_storage_client

__all__ = ["StorageClient", "get_storage_client"]

