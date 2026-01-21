"""
middleware/auth.py
认证和授权中间件
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config.settings import SETTINGS

# CSRF 序列化器
csrf_serializer = URLSafeTimedSerializer(SETTINGS.API_SECRET)


# Bearer Token 安全方案
security_scheme = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    config=Depends(lambda: SETTINGS),
):
    """
    验证 Bearer Token

    Args:
        credentials: HTTP Bearer 凭证
        config: 配置对象（通过依赖注入）

    Returns:
        验证通过的 token

    Raises:
        HTTPException: 如果 token 无效
    """
    token = credentials.credentials
    if token != config.API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def generate_csrf_token() -> str:
    """
    生成 CSRF token

    Returns:
        CSRF token 字符串
    """
    return csrf_serializer.dumps("csrf-protection", salt="csrf-salt")


def verify_csrf_token(token: str, max_age: int = 3600) -> bool:
    """
    验证 CSRF token

    Args:
        token: CSRF token 字符串
        max_age: token 最大有效期（秒）

    Returns:
        是否验证通过
    """
    try:
        csrf_serializer.loads(token, salt="csrf-salt", max_age=max_age)
        return True
    except (BadSignature, SignatureExpired):
        return False
