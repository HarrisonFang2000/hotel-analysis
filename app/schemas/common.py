"""
通用响应模型
统一API返回格式
"""
from pydantic import BaseModel
from typing import Any, Optional, Generic, TypeVar

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    
    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(code=200, message=message, data=data)
    
    @classmethod
    def error(cls, message: str, code: int = 500) -> "ApiResponse":
        return cls(code=code, message=message, data=None)


class PageResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    list: list[T]
    total: int
    page: int
    pageSize: int
