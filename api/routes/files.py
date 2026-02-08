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
from slowapi.util import get_remote_address

from api.dependencies import (
    get_archive_service,
    get_bandwidth_limiter,
    get_cache_wrapper,
)
from middleware.auth import verify_token
from middleware.bandwidth_limiter import BandwidthLimiter
from middleware.error_handler import BusinessException
from services.archive_service import ArchiveService
from services.file_parser import extract_text_from_upload_file
from utils.cache_fallback import CacheWithFallback

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Files"])

MAX_FILES_COUNT = 10


class ArchiveRequest(BaseModel):
    file_id: str
    summary: str = "User saved content"
    thread_id: str = "default"


@router.post("/upload", dependencies=[Depends(verify_token)])
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    cache: CacheWithFallback = Depends(get_cache_wrapper),
    bandwidth_limiter: BandwidthLimiter = Depends(get_bandwidth_limiter),
):
    # 速率限制检查
    client_ip = get_remote_address(request) or "127.0.0.1"
    try:
        limiter = request.app.state.limiter
        await limiter.check(client_ip, 1)  # 简单的请求计数
    except AttributeError:
        pass  # limiter 未配置，跳过

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
            raise BusinessException(
                message=f"Failed to process file '{file.filename}': {str(e)}",
                code="FILE_PROCESSING_ERROR",
                status_code=400,
            )

    await bandwidth_limiter.check(client_ip, total_processed_size)

    file_id = f"session_{uuid.uuid4().hex[:8]}"
    success = cache.setex(file_id, 3600, combined_text)

    if not success:
        logger.warning(f"⚠️ [Fallback] Cache write failed for {file_id}")

    return {"status": "success", "file_id": file_id, "file_count": len(files)}


@router.post("/archive", dependencies=[Depends(verify_token)])
async def archive_endpoint(
    request: Request,
    req: ArchiveRequest,
    background_tasks: BackgroundTasks,
    archive_service: ArchiveService = Depends(get_archive_service),
    cache: CacheWithFallback = Depends(get_cache_wrapper),
):
    # 速率限制检查
    client_ip = get_remote_address(request) or "127.0.0.1"
    try:
        limiter = request.app.state.limiter
        await limiter.check(client_ip, 1)
    except AttributeError:
        pass

    if not cache.exists(req.file_id):
        raise HTTPException(status_code=404, detail="Session expired or not found.")

    background_tasks.add_task(
        archive_service.archive_session,
        file_id=req.file_id,
        summary=req.summary,
        thread_id=req.thread_id,
    )
    return {"status": "queued"}
