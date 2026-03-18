import json
from functools import wraps
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

# 缓存配置：用户信息缓存1小时
USER_INFO_CACHE_TIMEOUT = 3600

def cache_user_info(timeout=USER_INFO_CACHE_TIMEOUT):
    """
    装饰器：缓存用户核心信息
    适用场景：查询用户信息的高频接口（如个人中心、权限校验）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            # 从User对象中获取user_id
            user_id = str(user.uuid)
            # 缓存键格式：user:{user_id}
            cache_key = f"user:{user_id}"

            # 2. 先查缓存：命中则直接返回
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data

            # 3. 缓存未命中：查数据库，再写入缓存
            try:
                user_data = func(user, *args, **kwargs)
                # 写入缓存（带过期时间）
                cache.set(cache_key, user_data, timeout)
                return user_data
            except ObjectDoesNotExist:
                # 避免缓存空值：设置短期空缓存（防止缓存穿透）
                cache.set(cache_key, None, 60)
                return None
        return wrapper
    return decorator

def clear_user_cache(user_id):
    """
    清除指定用户的缓存（用户信息修改/密码变更时调用）
    """
    # 缓存键格式：user:{user_id}
    cache_key = f"user:{user_id}"
    cache.delete(cache_key)