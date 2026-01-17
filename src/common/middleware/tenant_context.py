"""
TenantContext 中间件：租户上下文解析与校验

根据 tech.md §4.4.1：
1. 解析 X-Tenant-Id header
2. 校验 Tenant 存在
3. 校验 Tenant 状态为 ACTIVE（否则 403）
4. 校验 TenantUser 存在且为 ACTIVE（否则 403）
5. 将 tenant/tenant_user 挂载到 RequestContext

根据 tech.md §3.9.1：
- 租户侧接口（/api/*）：必须携带 X-Tenant-Id
- 平台后台接口（/admin/api/*）：不依赖 X-Tenant-Id
"""
import json
from typing import Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus
from apps.tenants.selectors import get_tenant_by_id, get_tenant_user
from common.errors.codes import ErrorCode
from common.http.response import resolve_request_id


TENANT_ID_HEADER = "X-Tenant-Id"
TENANT_ID_META_KEY = "HTTP_X_TENANT_ID"


class TenantContextMiddleware:
    """
    TenantContext 中间件
    
    在 AuthContext 之后执行，解析租户上下文并挂载到 request。
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 平台后台接口不依赖 X-Tenant-Id
        if request.path.startswith("/admin/api/") or request.path.startswith("/admin/"):
            return self.get_response(request)
        
        # 公开接口（如 /api/auth/login, /healthz）不需要租户上下文
        if self._is_public_path(request.path):
            return self.get_response(request)
        
        # 租户管理接口（获取租户列表、切换租户）不需要租户上下文
        # 因为这些接口本身就是用来获取和切换租户的
        if self._is_tenant_management_path(request.path):
            return self.get_response(request)
        
        # 解析 tenant_id
        tenant_id = self._extract_tenant_id(request)
        if tenant_id is None:
            # 租户侧接口必须携带 X-Tenant-Id
            return self._create_error_response(
                request=request,
                code=ErrorCode.BAD_REQUEST,
                message="缺少 X-Tenant-Id header",
                status_code=400,
            )
        
        # 校验并挂载租户上下文
        error_response = self._validate_and_attach_tenant(request, tenant_id)
        if error_response is not None:
            return error_response
        
        return self.get_response(request)
    
    def _is_public_path(self, path: str) -> bool:
        """判断是否为公开路径（不需要租户上下文）"""
        public_paths = [
            "/api/auth/",
            "/healthz",
            "/api/docs/",  # drf-spectacular 文档页面
            "/api/schema/",  # drf-spectacular schema
            "/favicon.ico",  # 静态资源
            "/static/",  # 静态文件
            "/media/",  # 媒体文件
            # /api/me 需要认证但可能不需要租户上下文（如果没有租户也可以返回基本信息）
            # 这里先允许通过，由视图层决定是否需要租户上下文
        ]
        return any(path.startswith(p) for p in public_paths)
    
    def _is_tenant_management_path(self, path: str) -> bool:
        """判断是否为租户管理路径（不需要租户上下文，因为这些接口本身就是用来获取和切换租户的）"""
        tenant_management_paths = [
            "/api/tenants",  # GET /api/tenants（租户列表）和 POST /api/tenants/switch（切换租户）
        ]
        # 精确匹配 /api/tenants 或 /api/tenants/switch
        return path in ["/api/tenants", "/api/tenants/"] or path.startswith("/api/tenants/switch")
    
    def _extract_tenant_id(self, request: HttpRequest) -> Optional[int]:
        """
        从请求中提取 tenant_id
        
        优先级：
        1. X-Tenant-Id header
        2. 如果用户已登录，可以从 last_tenant_id 获取（后续实现）
        """
        # 从 header 提取（支持 DRF Request 和 Django HttpRequest）
        header_value = None
        if hasattr(request, "headers"):
            # DRF Request 对象
            header_value = request.headers.get(TENANT_ID_HEADER)
        if not header_value and hasattr(request, "META"):
            # Django HttpRequest 对象
            header_value = request.META.get(TENANT_ID_META_KEY)
        
        if header_value:
            try:
                return int(header_value)
            except (ValueError, TypeError):
                return None
        
        # TODO: 如果用户已登录且没有提供 header，可以从 last_tenant_id 获取（T1.5）
        # 这里先返回 None，要求必须提供 header
        
        return None
    
    def _validate_and_attach_tenant(
        self, request: HttpRequest, tenant_id: int
    ) -> Optional[HttpResponse]:
        """
        校验租户并挂载到 request
        
        Returns:
            None 如果校验成功
            HttpResponse 如果校验失败（错误响应）
        """
        # 1. 校验 Tenant 存在
        tenant = get_tenant_by_id(tenant_id)
        if tenant is None:
            return self._create_error_response(
                request=request,
                code=ErrorCode.NOT_FOUND,
                message="租户不存在",
                status_code=404,
            )
        
        # 2. 校验 Tenant 状态为 ACTIVE
        if tenant.status != TenantStatus.ACTIVE:
            return self._create_error_response(
                request=request,
                code=ErrorCode.PERMISSION_DENIED,
                message="租户已停用",
                status_code=403,
            )
        
        # 3. 校验用户是否已登录（需要从 AuthContext 获取 user_id）
        user_id = self._get_user_id(request)
        if user_id is None:
            # 未登录用户不能访问租户侧接口（除非是公开接口，但公开接口不会走到这里）
            return self._create_error_response(
                request=request,
                code=ErrorCode.UNAUTHENTICATED,
                message="未登录",
                status_code=401,
            )
        
        # 4. 校验 TenantUser 存在且为 ACTIVE
        tenant_user = get_tenant_user(tenant_id, user_id)
        if tenant_user is None:
            return self._create_error_response(
                request=request,
                code=ErrorCode.PERMISSION_DENIED,
                message="用户不属于该租户",
                status_code=403,
            )
        
        if tenant_user.status != TenantUserStatus.ACTIVE:
            return self._create_error_response(
                request=request,
                code=ErrorCode.PERMISSION_DENIED,
                message="用户在该租户中已被禁用",
                status_code=403,
            )
        
        # 5. 挂载到 request
        request.tenant = tenant
        request.tenant_id = tenant_id
        request.tenant_user = tenant_user
        
        # 更新 last_login（可选，按需求）
        if tenant_user.last_login is None or (timezone.now() - tenant_user.last_login).total_seconds() > 3600:
            # 每小时更新一次 last_login，避免频繁写库
            tenant_user.last_login = timezone.now()
            tenant_user.save(update_fields=["last_login", "updated_at"])
        
        return None
    
    def _get_user_id(self, request: HttpRequest) -> Optional[int]:
        """
        从 request 获取 user_id（从 AuthContext 注入的 user）
        """
        if hasattr(request, "user") and request.user is not None:
            if hasattr(request.user, "is_authenticated") and request.user.is_authenticated:
                return getattr(request.user, "id", None) or getattr(request.user, "user_id", None)
        return None
    
    def _create_error_response(
        self,
        request: HttpRequest,
        code: ErrorCode | str,
        message: str,
        status_code: int,
    ) -> JsonResponse:
        """
        创建错误响应（使用 Django JsonResponse，兼容中间件层）
        """
        request_id = resolve_request_id(request)
        payload = {
            "code": str(code),
            "message": message,
            "data": None,
            "request_id": request_id,
        }
        response = JsonResponse(payload, status=status_code)
        response["X-Request-Id"] = request_id
        return response

