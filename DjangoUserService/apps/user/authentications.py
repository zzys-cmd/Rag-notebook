"""
认证模块：
    - JWTAuthentication: 认证类，从请求头中获取到JWT-Token并验证其有效性
        - authenticate： 从请求头中获取JWT Token并验证其有效性
        - authenticate_header： 在HTTP 401响应中返回认证方案

    - JWTTokenGenerator： 生成类，用户登录成功后，生成一个JWT-Token并返回
        - generate_token： 为用户生成JWT Token
        - refresh_token： 刷新Token（延长有效期）

"""

import time
import jwt
import uuid
from django.conf import settings
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import OfficeUser, UserStatusChoice

# 从jwt模块导入异常类
ExpiredSignatureError = jwt.ExpiredSignatureError
InvalidTokenError = getattr(jwt, 'InvalidTokenError', Exception)

class JWTAuthentication(BaseAuthentication):
    """JWT认证类，用于验证用户Token"""
    def authenticate(self, request) -> tuple[OfficeUser, str]:
        """
        从请求头中获取JWT Token并验证
        :param request: 请求对象
        :return: (user, token) 或者抛出AuthenticationFailed异常
        """
        # 从请求头中获取Authorization字段
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return None
        
        # 检查Authorization格式是否正确（Bearer token）
        try:
            auth_type, token = auth_header.split(' ', 1)
            if auth_type.lower() != 'bearer':
                raise AuthenticationFailed('认证类型错误，应为Bearer')
        except ValueError:
            raise AuthenticationFailed('认证头格式错误')
        
        # 验证并解码Token
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except ExpiredSignatureError:
            raise AuthenticationFailed('Token已过期，请重新登录')
        except jwt.InvalidSignatureError:
            raise AuthenticationFailed('无效的Token签名')
        except jwt.DecodeError:
            raise AuthenticationFailed('无法解码Token')
        except Exception:
            raise AuthenticationFailed('无效的Token')
        
        # 检查Token是否在黑名单中
        jti = payload.get('jti')
        if jti and cache.get(f'blacklist:{jti}'):
            raise AuthenticationFailed('Token已被撤销')
        
        # 从payload中获取用户ID
        user_id = payload.get('user_id')
        if not user_id:
            raise AuthenticationFailed('Token中未包含用户信息')
        
        # 获取用户对象 - 使用正确的字段名
        try:
            # OfficeUser使用uuid作为主键
            user = OfficeUser.objects.get(uuid=user_id)
        except OfficeUser.DoesNotExist:
            raise AuthenticationFailed('用户不存在')
        
        # 验证用户状态是否为激活
        if user.status != UserStatusChoice.ACTIVE:
            raise AuthenticationFailed('用户状态异常')
        
        return (user, token)
    
    def authenticate_header(self, request) -> str:
        """返回用于HTTP 401响应的value，用于识别认证方案"""
        return 'Bearer'


class JWTTokenGenerator:
    """JWT Token生成器，用于用户登录成功后生成Token"""

    @staticmethod
    def generate_token(user) -> tuple[str, int]:
        """
        为用户生成JWT Token
        :param user: 用户对象
        :return: (JWT Token字符串, 过期时间戳)
        """
        # 设置Token过期时间（默认为24小时）
        expire_time = int(time.time()) + 60 * 60 * 24  # 24小时后过期
        
        # 构建Payload
        payload = {
            'user_id': user.uuid,
            'username': user.username,
            'email': user.email,
            'exp': expire_time,
            'iat': int(time.time()),  # 签发时间
            'jti': str(uuid.uuid4())  # 唯一标识符
        }
        
        # 生成Token
        token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        # 处理Python 3.6+中jwt.encode返回bytes的情况
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        
        return token, expire_time
    
    @staticmethod
    def refresh_token(token) -> tuple[str, int]:
        """
        刷新Token（延长有效期）
        :param token: 原Token
        :return: 新Token和过期时间
        """
        try:
            # 不验证过期时间
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256'],
                options={'verify_exp': False}
            )
            
            # 创建新的Token，保留原始信息
            user_id = payload.get('user_id')
            if not user_id:
                raise ValueError('无效的Token')
            
            user = OfficeUser.objects.get(uuid=user_id)  # 修复为uuid
            return JWTTokenGenerator.generate_token(user)
            
        except Exception:
            raise AuthenticationFailed('Token刷新失败')
    
    @staticmethod
    def blacklist_token(token):
        """
        将Token添加到黑名单
        :param token: 要黑名单的Token
        """
        try:
            # 解码Token获取jti和过期时间
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256'],
                options={'verify_exp': False}
            )
            
            jti = payload.get('jti')
            exp = payload.get('exp')
            
            if jti and exp:
                # 计算Token剩余有效期
                current_time = int(time.time())
                ttl = exp - current_time if exp > current_time else 0
                
                # 将jti添加到Redis黑名单，设置过期时间为Token剩余有效期
                cache.set(f'blacklist:{jti}', '1', ttl)
                # 验证是否成功添加到黑名单
                if not cache.get(f'blacklist:{jti}'):
                    # 如果添加失败，尝试使用更长的过期时间
                    cache.set(f'blacklist:{jti}', '1', 60 * 60 * 24)  # 默认24小时
        except Exception as e:
            # 记录异常信息，便于调试
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"黑名单Token失败: {str(e)}")