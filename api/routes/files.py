import logging
import uuid
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import (
    get_archive_service,
    get_bandwidth_limiter,
    get_cache_wrapper,
)
from middleware.auth import verify_token
from middleware.bandwidth_limiter import BandwidthLimiter
from services.archive_service import ArchiveService
from services.file_parser import extract_text_from_upload_file
from utils.cache_fallback import CacheWithFallback

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Files"])

# ⚠️ 注意：Limiter 需要在 server.py 初始化并挂载到 app.state
# 这里我们创建一个占位符，或者通过 Depends 获取
# 为了简单，这里暂不使用装饰器限流，或使用全局 Limiter
limiter = Limiter(key_func=get_remote_address)

MAX_FILES_COUNT = 10


class ArchiveRequest(BaseModel):
    file_id: str
    summary: str = "User saved content"
    thread_id: str = "default"


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    cache: CacheWithFallback = Depends(get_cache_wrapper),
    bandwidth_limiter: BandwidthLimiter = Depends(get_bandwidth_limiter),
):
    client_ip = get_remote_address(request) or "127.0.0.1"

    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(status_code=413, detail="Too many files.")

    combined_text = ""
    total_processed_size = 0

    for file in files:
        logger.info(f"⚙️ Streaming processing: {file.filename}")
        try:
            text = await extract_text_from_upload_file(file)
            file_size_approx = len(text.encode("utf-8"))
            total_processed_size += file_size_approx

            if text:
                combined_text += f"\n\n--- FILE: {file.filename} ---\n{text}"
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error parsing {file.filename}: {e}")
            continue

    await bandwidth_limiter.check(client_ip, total_processed_size)

    file_id = f"session_{uuid.uuid4().hex[:8]}"
    success = cache.setex(file_id, 3600, combined_text)

    if not success:
        logger.warning(f"⚠️ [Fallback] Cache write failed for {file_id}")

    return {"status": "success", "file_id": file_id, "file_count": len(files)}


@router.post("/archive", dependencies=[Depends(verify_token)])
@limiter.limit("5/minute")
async def archive_endpoint(
    request: Request,
    req: ArchiveRequest,
    background_tasks: BackgroundTasks,
    archive_service: ArchiveService = Depends(get_archive_service),
    cache: CacheWithFallback = Depends(get_cache_wrapper),
):
    if not cache.exists(req.file_id):
        raise HTTPException(status_code=404, detail="Session expired or not found.")

    background_tasks.add_task(
        archive_service.archive_session,
        file_id=req.file_id,
        summary=req.summary,
        thread_id=req.thread_id,
    )
    return {"status": "queued"}
