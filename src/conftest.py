"""
pytest 启动期补丁：修复 import_string 使用 rsplit。
"""
from importlib import import_module


def _patched_import_string(dotted_path: str):
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module_loading = import_module("django.utils.module_loading")
    try:
        return module_loading.cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        ) from err


def pytest_load_initial_conftests(*args, **kwargs):
    """
    在 pytest-django 初始化 Django 之前，修复 import_string。
    """
    try:
        module_loading = import_module("django.utils.module_loading")
        module_loading.import_string = _patched_import_string
    except Exception:
        pass

    # 若 django.db.models.options 已加载，则一并替换本地引用
    try:
        options_module = import_module("django.db.models.options")
        options_module.import_string = _patched_import_string
    except Exception:
        pass
