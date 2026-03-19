from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status


def rate_limit(limit: int = 1, window: int = 60) -> callable:
    """
    限流装饰器
    :param limit: 时间窗口内的最大请求数
    :param window: 时间窗口大小（秒）
    :return: 装饰器
    """
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            # 获取客户端IP
            client_ip = request.META.get('REMOTE_ADDR')
            if not client_ip:
                client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or 'unknown'
            
            # 生成限流键
            key = f"rate_limit:register:{client_ip}"
            
            # 获取当前计数
            current = cache.get(key, 0)
            
            if current >= limit:
                # 限流触发
                return Response(
                    {"detail": "请求过于频繁，请稍后再试"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            
            # 增加计数
            if current == 0:
                # 第一次请求，设置过期时间
                cache.set(key, 1, window)
            else:
                # 后续请求，增加计数
                cache.incr(key)
            
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator