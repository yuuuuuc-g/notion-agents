"""
middleware/auth.py
认证和授权中间件
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import SETTINGS

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
