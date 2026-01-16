from http import HTTPStatus

from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_default_exception_handler

from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException
from common.http.response import envelope_response


STATUS_CODE_TO_ERROR = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.UNAUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.PERMISSION_DENIED,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_412_PRECONDITION_FAILED: ErrorCode.PRECONDITION_FAILED,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.INTERNAL_ERROR,
}


def _first_error_message(detail) -> str:
    """
    尝试从 ValidationError detail 中提取首条可读提示。
    """
    if detail is None:
        return ""
    if isinstance(detail, (list, tuple)) and detail:
        return _first_error_message(detail[0])
    if isinstance(detail, dict) and detail:
        first_value = next(iter(detail.values()))
        return _first_error_message(first_value)
    return str(detail)


def _error_code_from_status(status_code: int) -> ErrorCode:
    return STATUS_CODE_TO_ERROR.get(status_code, ErrorCode.INTERNAL_ERROR)


def _reason_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def drf_exception_handler(exc, context):
    """
    将 DRF/Django 异常转换为统一壳响应。
    """
    request = context.get("request")

    if isinstance(exc, GrassAPIException):
        return envelope_response(
            exc.data,
            code=exc.error_code,
            message=str(exc.detail),
            status_code=exc.status_code,
            request=request,
        )

    if isinstance(exc, ValidationError):
        return envelope_response(
            exc.detail,
            code=ErrorCode.BAD_REQUEST,
            message=_first_error_message(exc.detail) or "Invalid request.",
            status_code=status.HTTP_400_BAD_REQUEST,
            request=request,
        )

    if isinstance(exc, NotAuthenticated):
        return envelope_response(
            None,
            code=ErrorCode.UNAUTHENTICATED,
            message=_first_error_message(exc.detail) or "Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            request=request,
        )

    if isinstance(exc, PermissionDenied):
        return envelope_response(
            None,
            code=ErrorCode.PERMISSION_DENIED,
            message=_first_error_message(exc.detail) or "Permission denied.",
            status_code=status.HTTP_403_FORBIDDEN,
            request=request,
        )

    if isinstance(exc, Http404):
        return envelope_response(
            None,
            code=ErrorCode.NOT_FOUND,
            message=str(exc) or "Not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            request=request,
        )

    if isinstance(exc, IntegrityError):
        return envelope_response(
            None,
            code=ErrorCode.CONFLICT,
            message=str(exc) or "Resource conflict.",
            status_code=status.HTTP_409_CONFLICT,
            request=request,
        )

    # 交给 DRF 默认处理其他 APIException，再包裹统一壳
    drf_response = drf_default_exception_handler(exc, context)
    if drf_response is not None:
        message = _first_error_message(getattr(drf_response, "data", None))
        status_code = drf_response.status_code
        return envelope_response(
            None,
            code=_error_code_from_status(status_code),
            message=message or _reason_phrase(status_code),
            status_code=status_code,
            request=request,
        )

    # 未捕获异常 → 500
    return envelope_response(
        None,
        code=ErrorCode.INTERNAL_ERROR,
        message=str(exc) or "Internal server error.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request=request,
    )
