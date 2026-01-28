from fastapi import APIRouter, Depends

from api.dependencies import get_settings, get_sync_service
from middleware.error_handler import BusinessException
from services.sync_service import SyncService

router = APIRouter(tags=["Admin"])


@router.post("/sync_notion")
async def sync_notion(
    sync_service: SyncService = Depends(get_sync_service), config=Depends(get_settings)
):
    if not config.DB_SPANISH_ID:
        raise BusinessException(
            message="No DB ID configured", code="CONFIG_ERROR", status_code=400
        )

    result = await sync_service.sync_database(db_id=config.DB_SPANISH_ID)
    return result
