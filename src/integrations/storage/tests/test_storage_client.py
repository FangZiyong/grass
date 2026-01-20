"""
StorageClient 单元测试
覆盖 LOCAL put/get、路径穿越防护、非法 content-type、异常映射
"""

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from common.errors.codes import ErrorCode
from integrations.storage.client import (
    LocalStorageClient,
    S3StorageClient,
    StorageError,
    get_storage_client,
)


class LocalStorageClientTest(TestCase):
    """本地存储客户端测试"""

    def test_put_bytes_success(self):
        """测试成功上传字节数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")
            key = "test/file.txt"
            data = b"Hello, World!"

            file_url = client.put_bytes(key, data, content_type="text/plain")

            # 验证文件已创建
            file_path = Path(tmpdir) / key
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), data)

            # 验证返回的 URL
            self.assertEqual(file_url, "/storage/test/file.txt")

    def test_put_file_success(self):
        """测试成功上传文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            # 创建源文件
            source_file = Path(tmpdir) / "source.txt"
            source_file.write_text("Source content")

            key = "uploaded/file.txt"
            file_url = client.put_file(key, source_file, content_type="text/plain")

            # 验证文件已上传
            uploaded_path = Path(tmpdir) / key
            self.assertTrue(uploaded_path.exists())
            self.assertEqual(uploaded_path.read_text(), "Source content")

            # 验证返回的 URL
            self.assertEqual(file_url, "/storage/uploaded/file.txt")

    def test_put_file_source_not_exists(self):
        """测试上传不存在的源文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")
            source_file = Path(tmpdir) / "nonexistent.txt"
            key = "uploaded/file.txt"

            with self.assertRaises(StorageError) as cm:
                client.put_file(key, source_file)

            self.assertEqual(cm.exception.status_code, 404)
            self.assertEqual(cm.exception.error_code, ErrorCode.NOT_FOUND)

    def test_put_file_source_is_directory(self):
        """测试上传目录而非文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")
            source_dir = Path(tmpdir) / "source_dir"
            source_dir.mkdir()
            key = "uploaded/file.txt"

            with self.assertRaises(StorageError) as cm:
                client.put_file(key, source_dir)

            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.error_code, ErrorCode.BAD_REQUEST)

    def test_path_traversal_prevention(self):
        """测试路径穿越防护"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            # 测试 ../ 路径穿越
            with self.assertRaises(StorageError) as cm:
                client.put_bytes("../../etc/passwd", b"malicious")

            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.error_code, ErrorCode.BAD_REQUEST)
            self.assertIn("path traversal", str(cm.exception.detail).lower())

            # 测试 /../ 路径穿越
            with self.assertRaises(StorageError) as cm:
                client.put_bytes("normal/../../etc/passwd", b"malicious")

            self.assertEqual(cm.exception.status_code, 400)

            # 测试 .. 开头
            with self.assertRaises(StorageError) as cm:
                client.put_bytes("../test", b"data")

            self.assertEqual(cm.exception.status_code, 400)

    def test_empty_key_rejection(self):
        """测试空键拒绝"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            with self.assertRaises(StorageError) as cm:
                client.put_bytes("", b"data")

            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.error_code, ErrorCode.BAD_REQUEST)

    def test_whitespace_key_rejection(self):
        """测试包含首尾空白的键拒绝"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            with self.assertRaises(StorageError) as cm:
                client.put_bytes("  test  ", b"data")

            self.assertEqual(cm.exception.status_code, 400)

    def test_invalid_content_type(self):
        """测试非法 content-type"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            # 测试包含分号的 content-type
            with self.assertRaises(StorageError) as cm:
                client.put_bytes("test.txt", b"data", content_type="text/plain; charset=utf-8")

            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.error_code, ErrorCode.BAD_REQUEST)

            # 测试包含换行符的 content-type
            with self.assertRaises(StorageError) as cm:
                client.put_bytes("test.txt", b"data", content_type="text/plain\n")

            self.assertEqual(cm.exception.status_code, 400)

    def test_get_presigned_url(self):
        """测试获取预签名 URL（本地模式直接返回 file_url）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")
            key = "test/file.txt"

            url = client.get_presigned_url(key, expires_in=3600)

            self.assertEqual(url, "/storage/test/file.txt")

    def test_normalize_key_path(self):
        """测试键路径规范化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")

            # 测试前导斜杠被移除
            file_url1 = client.put_bytes("/test/file.txt", b"data")
            assert file_url1 == "/storage/test/file.txt"

            # 测试多个斜杠被规范化
            file_url2 = client.put_bytes("test//file.txt", b"data")
            assert file_url2 == "/storage/test/file.txt"

            # 验证文件确实存在
            self.assertTrue((Path(tmpdir) / "test" / "file.txt").exists())

    def test_create_parent_directories(self):
        """测试自动创建父目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=tmpdir, base_url="/storage/")
            key = "deep/nested/path/file.txt"
            data = b"content"

            client.put_bytes(key, data)

            file_path = Path(tmpdir) / key
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), data)


class S3StorageClientTest(TestCase):
    """S3 存储客户端测试（mock 实现）"""

    def test_put_bytes_mock(self):
        """测试 S3 put_bytes（mock 实现）"""
        client = S3StorageClient(
            endpoint_url="https://s3.example.com",
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        file_url = client.put_bytes("test/file.txt", b"data", content_type="text/plain")

        # Mock 实现返回占位 URL
        self.assertEqual(file_url, "https://s3.example.com/test-bucket/test/file.txt")

    def test_put_file_mock(self):
        """测试 S3 put_file（mock 实现）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = S3StorageClient(
                endpoint_url="https://s3.example.com",
                bucket_name="test-bucket",
                access_key_id="test-key",
                secret_access_key="test-secret",
            )

            source_file = Path(tmpdir) / "source.txt"
            source_file.write_text("source content")

            file_url = client.put_file("test/file.txt", source_file)

            self.assertEqual(file_url, "https://s3.example.com/test-bucket/test/file.txt")

    def test_put_file_source_not_exists(self):
        """测试 S3 put_file 源文件不存在"""
        client = S3StorageClient(
            endpoint_url="https://s3.example.com",
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = Path(tmpdir) / "nonexistent.txt"

            with self.assertRaises(StorageError) as cm:
                client.put_file("test/file.txt", source_file)

            self.assertEqual(cm.exception.status_code, 404)
            self.assertEqual(cm.exception.error_code, ErrorCode.NOT_FOUND)

    def test_get_presigned_url_mock(self):
        """测试 S3 get_presigned_url（mock 实现）"""
        client = S3StorageClient(
            endpoint_url="https://s3.example.com",
            bucket_name="test-bucket",
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

        url = client.get_presigned_url("test/file.txt", expires_in=3600)

        # Mock 实现返回占位 URL
        self.assertIn("test/file.txt", url)
        self.assertIn("expires=3600", url)


class GetStorageClientTest(TestCase):
    """测试 get_storage_client 工厂函数"""

    @override_settings(
        STORAGE_TYPE="LOCAL",
        STORAGE_LOCAL_BASE_DIR=None,
        STORAGE_LOCAL_BASE_URL="/storage/",
    )
    def test_get_local_storage_client(self):
        """测试获取本地存储客户端"""
        client = get_storage_client()

        self.assertIsInstance(client, LocalStorageClient)

    @override_settings(
        STORAGE_TYPE="LOCAL",
        STORAGE_LOCAL_BASE_DIR="/tmp/test-storage",
        STORAGE_LOCAL_BASE_URL="/custom-storage/",
    )
    def test_get_local_storage_client_with_custom_config(self):
        """测试使用自定义配置获取本地存储客户端"""
        client = get_storage_client()

        self.assertIsInstance(client, LocalStorageClient)
        self.assertEqual(client.base_dir, Path("/tmp/test-storage"))
        self.assertEqual(client.base_url, "/custom-storage/")

    @override_settings(
        STORAGE_TYPE="S3",
        STORAGE_S3_ENDPOINT_URL="https://s3.example.com",
        STORAGE_S3_BUCKET_NAME="test-bucket",
        STORAGE_S3_ACCESS_KEY_ID="test-key",
        STORAGE_S3_SECRET_ACCESS_KEY="test-secret",
        STORAGE_S3_REGION="us-west-2",
    )
    def test_get_s3_storage_client(self):
        """测试获取 S3 存储客户端"""
        client = get_storage_client()

        self.assertIsInstance(client, S3StorageClient)
        self.assertEqual(client.endpoint_url, "https://s3.example.com")
        self.assertEqual(client.bucket_name, "test-bucket")
        self.assertEqual(client.region, "us-west-2")

    @override_settings(
        STORAGE_TYPE="S3",
        STORAGE_S3_ENDPOINT_URL="",
        STORAGE_S3_BUCKET_NAME="",
        STORAGE_S3_ACCESS_KEY_ID="",
        STORAGE_S3_SECRET_ACCESS_KEY="",
    )
    def test_get_s3_storage_client_incomplete_config(self):
        """测试 S3 配置不完整时抛出异常"""
        with self.assertRaises(StorageError) as cm:
            get_storage_client()

        self.assertEqual(cm.exception.status_code, 500)
        self.assertIn("incomplete", str(cm.exception.detail).lower())

    @override_settings(STORAGE_TYPE="INVALID")
    def test_get_storage_client_unsupported_type(self):
        """测试不支持的存储类型"""
        with self.assertRaises(StorageError) as cm:
            get_storage_client()

        self.assertEqual(cm.exception.status_code, 500)
        self.assertIn("unsupported", str(cm.exception.detail).lower())
