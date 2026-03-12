import os
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

# Django JWT配置
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# 创建Bearer认证方案
security = HTTPBearer()


def decode_django_jwt(token: str) -> Optional[Dict[str, Any]]:
    """解析Django生成的JWT token
    
    Args:
        token: JWT token字符串
        
    Returns:
        解析后的payload，如果解析失败返回None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从Django JWT中获取当前用户UUID
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        用户的UUID
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    token = credentials.credentials
    payload = decode_django_jwt(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 从Django JWT中提取user_id（uuid）
    user_id: str = payload.get("user_id")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not find user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id