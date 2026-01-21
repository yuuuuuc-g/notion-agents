from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import get_audio_service, get_cache_wrapper, get_chat_service
from middleware.auth import verify_token
from services.audio_service import AudioService
from services.chat_service import ChatService
from utils.cache_fallback import CacheWithFallback

router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default_user"
    file_id: Optional[str] = None
    model_name: Optional[str] = "deepseek/deepseek-chat"


@router.post("/chat", dependencies=[Depends(verify_token)])
async def chat_endpoint(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    cache: CacheWithFallback = Depends(get_cache_wrapper),
):
    """
    智能对话接口
    """
    context = ""
    if body.file_id:
        cached_text = cache.get(body.file_id)
        if cached_text:
            context = cached_text[:20000]

    response_stream = chat_service.stream_response(
        query=body.query,
        thread_id=body.thread_id,
        model_name=body.model_name,
        context=context,
    )
    return StreamingResponse(response_stream, media_type="text/plain")


@router.post("/tts", dependencies=[Depends(verify_token)])
async def text_to_speech(
    text: str, audio_service: AudioService = Depends(get_audio_service)
):
    """
    文本转语音接口 (TTS)
    """
    url = await audio_service.generate_audio_file(text)
    if not url:
        return {"error": "Failed to generate audio"}
    return {"url": url}
