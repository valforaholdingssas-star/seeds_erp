from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class SeedsAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "seeds_error"
    default_detail = "Error en la operación."


class ConfigurationError(SeedsAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "configuration_error"


def seeds_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        payload = {"detail": detail["detail"], "code": getattr(exc, "default_code", "error")}
    else:
        payload = {"detail": detail, "code": getattr(exc, "default_code", "error")}
    return Response(payload, status=response.status_code)
