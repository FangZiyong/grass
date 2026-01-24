import os
from pathlib import Path

from dotenv import load_dotenv

# 自定义日志配置
from config.logging import LOGGING as LOGGING_SETTINGS

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
    "config.apps.ConfigConfig",  # 确保在 Django setup 后重新加载 DRF 配置
    # 业务应用
    "apps.accounts",
    "apps.tenants",
    "apps.iam",
    "apps.execution",
    "apps.resource_tree",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.middleware.request_id.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # TenantContext 必须在 AuthContext 之后执行（因为需要 user_id）
    # 但 AuthContext 是通过 DRF Authentication 实现的，在中间件之后执行
    # 所以这里先放在 AuthenticationMiddleware 之后，实际执行顺序由 DRF 决定
    "common.middleware.tenant_context.TenantContextMiddleware",
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
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.middleware.auth_context.JWTAuthentication",
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
    # Swagger UI 的 Authorize 按钮依赖 OpenAPI 的 components.securitySchemes 定义
    # scheme 名称需与 SECURITY 中引用的名称一致
    "SECURITY": [{"bearerAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        # 响应体里包含超长 token 时，swagger-ui 的高亮渲染在部分浏览器会卡顿/空白
        # 关闭高亮能让 Response body 更稳定地展示
        "syntaxHighlight": {"activated": False},
    },
}

# LOGGING_CONFIG 使用 Django 默认 dictConfig
LOGGING_CONFIG = "logging.config.dictConfig"
LOGGING = LOGGING_SETTINGS

# JWT 配置
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

# Celery 配置
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30分钟
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25分钟

# DRF 配置初始化
# 
# 问题：DRF 的 api_settings 在模块导入时就被创建，此时 Django 可能还没有 setup，
# 导致 settings.REST_FRAMEWORK 可能不存在，api_settings.user_settings 会缓存空字典。
# 
# 解决方案：在 Django setup 后重新加载 DRF 配置。
# 这个逻辑在 AppConfig.ready() 中执行，确保在所有情况下都能正确加载。
def _reload_drf_settings():
    """重新加载 DRF 配置，确保使用正确的 settings.REST_FRAMEWORK"""
    try:
        from rest_framework.settings import api_settings
        api_settings.reload()
    except ImportError:
        pass


# 存储配置
STORAGE_TYPE = os.environ.get("STORAGE_TYPE", "LOCAL").upper()  # LOCAL | S3

# LOCAL 存储配置
STORAGE_LOCAL_BASE_DIR = os.environ.get("STORAGE_LOCAL_BASE_DIR", None)  # 默认使用项目根目录下的 storage
STORAGE_LOCAL_BASE_URL = os.environ.get("STORAGE_LOCAL_BASE_URL", "/storage/")

# S3 存储配置（可选）
STORAGE_S3_ENDPOINT_URL = os.environ.get("STORAGE_S3_ENDPOINT_URL", "")
STORAGE_S3_BUCKET_NAME = os.environ.get("STORAGE_S3_BUCKET_NAME", "")
STORAGE_S3_ACCESS_KEY_ID = os.environ.get("STORAGE_S3_ACCESS_KEY_ID", "")
STORAGE_S3_SECRET_ACCESS_KEY = os.environ.get("STORAGE_S3_SECRET_ACCESS_KEY", "")
STORAGE_S3_REGION = os.environ.get("STORAGE_S3_REGION", "us-east-1")

