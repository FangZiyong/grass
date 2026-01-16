import os
from pathlib import Path

from dotenv import load_dotenv

# 自定义日志配置（避免覆盖 Django 默认 LOGGING_CONFIG）
from config.logging import LOGGING as LOGGING_SETTINGS
from django.utils import module_loading as django_module_loading
from django.utils import log as django_log


def _import_string_compatible(dotted_path: str):
    """
    兼容 import_string：支持多段 dotted path（取最后一段作为属性名）。
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err
    return django_module_loading.cached_import(module_path, class_name)


# 覆盖 Django 内部 import_string，避免 split(".", 1) 造成的导入失败
django_module_loading.import_string = _import_string_compatible
# django.utils.log 在导入时会绑定 import_string，需要同步替换
django_log.import_string = _import_string_compatible

BASE_DIR = Path(__file__).resolve().parent.parent.parent
project_root = BASE_DIR.parent

env_file = os.environ.get("ENV_FILE")
if env_file:
    load_dotenv(env_file)
else:
    default_env = project_root / ".env.dev"
    fallback_env = project_root / ".env"
    load_dotenv(default_env if default_env.exists() else fallback_env)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = (
    [host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host] or ["*"]
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.middleware.request_id.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.environ.get("DJANGO_DB_ENGINE", "django.db.backends.mysql")
DEFAULT_DB_NAME = os.environ.get("DJANGO_DB_NAME", "grass")

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DEFAULT_DB_NAME,
        "USER": os.environ.get("DJANGO_DB_USER", ""),
        "PASSWORD": os.environ.get("DJANGO_DB_PASSWORD", ""),
        "HOST": os.environ.get("DJANGO_DB_HOST", ""),
        "PORT": os.environ.get("DJANGO_DB_PORT", "3306"),
    }
}

if "mysql" in DB_ENGINE:
    DATABASES["default"]["OPTIONS"] = {
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "EXCEPTION_HANDLER": "common.errors.handlers.drf_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "common.http.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Grass API",
    "DESCRIPTION": "API schema for Grass backend",
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": True,
}

LOGGING = LOGGING_SETTINGS

