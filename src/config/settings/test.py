from .base import *  # noqa: F401,F403

# Test-only overrides.
DEBUG = False

# 避免 pytest 下 logging.config 导入冲突
LOGGING_CONFIG = None

# 修复 pytest 启动期 import_string 的 split 逻辑
from django.utils import module_loading


def _patched_import_string(dotted_path: str):
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    try:
        return cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        ) from err


# 原地替换 import_string 的函数体，影响所有已导入引用
module_loading.import_string.__code__ = _patched_import_string.__code__
module_loading.import_string.__defaults__ = _patched_import_string.__defaults__
module_loading.import_string.__kwdefaults__ = _patched_import_string.__kwdefaults__

# pytest 下 AppConfig 解析兼容（避免 class path 解析异常）
INSTALLED_APPS = [
    "config" if app == "config.apps.ConfigConfig" else app for app in INSTALLED_APPS
]

# 使用 sqlite 内存库，避免依赖外部 MySQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
