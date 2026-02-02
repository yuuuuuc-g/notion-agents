"""
services/audio_service.py
音频生成服务 (Text-to-Speech)
功能：集成了智能长文本切分 + Markdown清洗 + 手动停顿控制 + Pydub混音
"""
import os
import re
import uuid

import edge_tts
from pydub import AudioSegment

from utils.logger import get_logger

logger = get_logger(__name__)


class AudioService:
    def __init__(self, config):
        """
        初始化音频服务
        Args:
            config: 全局配置对象 (Settings)
        """
        self.config = config
        self.audio_dir = config.AUDIO_DIR
        self.rate = config.TTS_RATE

        # 确保目录存在
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)

        # 常量定义
        self.PAUSE_MARKER = "==="
        self.PAUSE_DURATION_MS = 2000
        self.MAX_CHUNK_SIZE = 1500

    def clean_text(self, text: str) -> str:
        """
        清洗文本：去除 Markdown 符号和干扰字符，但保留标点
        """
        if not text:
            return ""
        text = re.sub(r"[\*\#]", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"\-{2,}", "", text)
        return text.strip()

    async def _generate_segment_file(
        self, text: str, voice: str, filename: str
    ) -> bool:
        """生成单个音频片段文件"""
        try:
            communicate = edge_tts.Communicate(text, voice, rate=self.rate)
            await communicate.save(filename)
            return True
        except Exception as e:
            logger.error(f"⚠️ Segment generation failed: {e}")
            return False

    def _smart_split_long_text(self, text: str) -> list[str]:
        """如果一段话太长，再次进行强制切分"""
        limit = self.MAX_CHUNK_SIZE
        if len(text) < limit:
            return [text]
        chunks = []
        for i in range(0, len(text), limit):
            chunks.append(text[i : i + limit])
        return chunks

    async def generate_audio_file(self, text: str, language: str = "es") -> str | None:
        """
        核心入口：文本转语音
        """
        if not text:
            return None

        # 1. 自动选择语音包
        voice_map = {
            "en": "en-US-AriaNeural",
            "zh": "zh-CN-XiaoxiaoNeural",
            "es": "es-MX-DaliaNeural",
            "ja": "ja-JP-NanamiNeural",
        }
        voice = voice_map.get(language, "es-MX-DaliaNeural")

        final_audio = AudioSegment.empty()
        silence_audio = AudioSegment.silent(duration=self.PAUSE_DURATION_MS)
        raw_sections = text.split(self.PAUSE_MARKER)

        temp_files_to_cleanup = []

        try:
            logger.info(f"🎤 Processing audio generation ({len(text)} chars)...")

            for i, section_raw in enumerate(raw_sections):
                clean_section = self.clean_text(section_raw)
                if not clean_section:
                    continue

                sub_chunks = self._smart_split_long_text(clean_section)
                section_audio = AudioSegment.empty()

                for chunk in sub_chunks:
                    temp_filename = os.path.join(
                        self.audio_dir, f"temp_{uuid.uuid4().hex}.mp3"
                    )
                    success = await self._generate_segment_file(
                        chunk, voice, temp_filename
                    )

                    if success:
                        temp_files_to_cleanup.append(temp_filename)
                        chunk_audio = AudioSegment.from_mp3(temp_filename)
                        section_audio += chunk_audio

                final_audio += section_audio

                if i < len(raw_sections) - 1:
                    final_audio += silence_audio

            # 4. 导出最终文件
            # 使用相对路径还是绝对路径取决于你的前端怎么访问
            # 这里返回相对路径的文件名，或者完整路径
            filename_only = f"audio_{uuid.uuid4().hex[:8]}.mp3"
            final_path = os.path.join(self.audio_dir, filename_only)

            final_audio.export(final_path, format="mp3")
            logger.info(f"✅ Audio saved: {final_path}")

            # 返回给前端的 URL 路径 (假设挂载在 /audio 下)
            return f"/generated_audio/{filename_only}"

        except Exception as e:
            logger.error(f"❌ Audio generation error: {str(e)}")
            return None
        finally:
            # 5. 清理临时文件
            for f in temp_files_to_cleanup:
                if os.path.exists(f):
                    os.remove(f)
