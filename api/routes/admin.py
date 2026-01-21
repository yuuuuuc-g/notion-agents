from fastapi import APIRouter, Depends

from api.dependencies import get_settings, get_sync_service
from services.sync_service import SyncService

router = APIRouter(tags=["Admin"])


@router.post("/sync_notion")
async def sync_notion(
    sync_service: SyncService = Depends(get_sync_service), config=Depends(get_settings)
):
    if not config.DB_SPANISH_ID:
        return {"status": "error", "message": "No DB ID configured"}

    result = await sync_service.sync_database(db_id=config.DB_SPANISH_ID)
    return result
