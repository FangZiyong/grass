"""
兼容修复：django.utils.module_loading.import_string 使用 rsplit。

当前环境的 import_string 只做 split(".", 1)，会导致无法解析多段模块路径。
该补丁在 Python 启动时自动加载，确保 Django/DRF 的 dotted path 可用。
"""
from importlib import import_module


def _patch_django_import_string() -> None:
    try:
        module_loading = import_module("django.utils.module_loading")
    except Exception:
        return

    def import_string(dotted_path: str):
        try:
            module_path, class_name = dotted_path.rsplit(".", 1)
        except ValueError as err:
            raise ImportError(f"{dotted_path} doesn't look like a module path") from err

        try:
            return module_loading.cached_import(module_path, class_name)
        except AttributeError as err:
            raise ImportError(
                f'Module "{module_path}" does not define a "{class_name}" attribute/class'
            ) from err

    module_loading.import_string = import_string


_patch_django_import_string()
