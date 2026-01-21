"""
tests/unit/test_audio_service.py
音频服务单元测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.audio_service import AudioService


@pytest.fixture
def audio_service(mock_settings):
    # 确保临时目录存在
    mock_settings.AUDIO_DIR = "/tmp/test_audio"
    return AudioService(mock_settings)


@pytest.mark.asyncio
async def test_generate_audio_file_success(audio_service):
    """测试正常的音频生成流程"""
    text = "Hola mundo. === Pause."

    # Mock edge_tts
    with patch("services.audio_service.edge_tts.Communicate") as MockComm:
        mock_comm_instance = MockComm.return_value
        mock_comm_instance.save = AsyncMock(return_value=True)

        # Mock pydub (避免处理真实音频文件)
        with patch("services.audio_service.AudioSegment") as MockAudio:
            # 模拟空音频和静音
            MockAudio.empty.return_value = MagicMock()
            MockAudio.silent.return_value = MagicMock()
            MockAudio.from_mp3.return_value = MagicMock()

            # Mock os.path.exists 和 remove 以跳过文件操作
            with patch("os.path.exists", return_value=True):
                with patch("os.remove"):
                    # Mock export
                    MockAudio.empty.return_value.export = MagicMock()

                    result = await audio_service.generate_audio_file(text, "es")

                    assert result is not None
                    assert "audio_" in result
                    assert result.endswith(".mp3")


@pytest.mark.asyncio
async def test_generate_audio_empty_text(audio_service):
    """测试空文本"""
    result = await audio_service.generate_audio_file("")
    assert result is None


def test_clean_text(audio_service):
    """测试文本清洗"""
    raw = "**Hello** [Link](http://url) --"
    cleaned = audio_service.clean_text(raw)
    assert cleaned == "Hello Link"
