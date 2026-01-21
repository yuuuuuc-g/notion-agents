import redis
from fastapi import APIRouter, Depends

from api.dependencies import get_redis, get_settings
from middleware.auth import generate_csrf_token

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check(
    redis_conn: redis.Redis = Depends(get_redis), settings=Depends(get_settings)
):
    try:
        redis_conn.ping()
        status_redis = "connected"
    except Exception:
        status_redis = "error"
    return {
        "status": "ok",
        "version": "3.4.0",
        "redis": status_redis,
        "env": settings.ENVIRONMENT,
    }


@router.get("/csrf-token")
async def get_csrf_token_endpoint():
    return {"csrf_token": generate_csrf_token()}
