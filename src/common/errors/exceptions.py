from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException

from common.errors.codes import ErrorCode


class GrassAPIException(APIException):
    """
    统一业务异常基类，携带错误码与可选的数据负载。
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request"
    default_code = ErrorCode.BAD_REQUEST
    error_code: ErrorCode | str = ErrorCode.BAD_REQUEST
    data: Any = None

    def __init__(
        self,
        detail: str | None = None,
        *,
        status_code: int | None = None,
        code: ErrorCode | str | None = None,
        data: Any = None,
    ):
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.error_code = code
        if data is not None:
            self.data = data

        super().__init__(detail=detail or self.default_detail, code=str(self.error_code))
