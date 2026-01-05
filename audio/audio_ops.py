"""
audio_ops.py - Pro Version
集成了：智能长文本切分 + Markdown清洗 + 手动停顿控制 + Pydub混音
"""
import os
import uuid
import re
import asyncio
import edge_tts
from pydub import AudioSegment
from config.settings import SETTINGS

# --- 配置区域 ---

AUDIO_DIR = SETTINGS.AUDIO_DIR
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

RATE = SETTINGS.TTS_RATE 
PAUSE_MARKER = "==="
PAUSE_DURATION_MS = 2000 
MAX_CHUNK_SIZE = 1500

def clean_text(text: str) -> str:
    """
    清洗文本：去除 Markdown 符号和干扰字符，但保留标点
    """
    if not text: return ""

    text = re.sub(r"[\*\#]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\-{2,}", "", text)

    return text.strip()

async def _generate_segment_file(text: str, voice: str, filename: str) -> bool:
    """生成单个音频片段文件"""
    try:
        communicate = edge_tts.Communicate(text, voice, rate=RATE)
        await communicate.save(filename)
        return True
    except Exception as e:
        print(f"⚠️ Segment generation failed: {e}")
        return False

def _smart_split_long_text(text: str, limit: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    如果一段话太长（超过 limit），再次进行强制切分，防止 503 错误
    """
    if len(text) < limit:
        return [text]
    
    chunks = []
    # 简单按句号切分，如果还不够细，就按长度硬切
    # 这里为了代码简洁，采用按长度安全切分
    for i in range(0, len(text), limit):
        chunks.append(text[i:i+limit])
    return chunks

async def generate_audio_file(text: str, language: str = 'es') -> str | None:
    """
    核心入口：文本转语音 (支持 === 停顿符, Markdown 清洗, 长文本自动切分)
    """
    if not text: return None

    # 1. 自动选择语音包
    voice_map = {
        'en': 'en-US-AriaNeural',
        'zh': 'zh-CN-XiaoxiaoNeural', 
        'es': 'es-MX-DaliaNeural',
        'ja': 'ja-JP-NanamiNeural'
    }
    voice = voice_map.get(language, 'es-MX-DaliaNeural')

    # 2. 准备最终容器
    final_audio = AudioSegment.empty()
    silence_audio = AudioSegment.silent(duration=PAUSE_DURATION_MS)
    
    # 3. 第一层切分：按用户的手动停顿符 (===) 切分
    # 这样我们可以保证在用户想要停顿的地方插入 silence
    raw_sections = text.split(PAUSE_MARKER)
    
    temp_files_to_cleanup = [] # 记录临时文件以便删除

    try:
        print(f"🎤 Processing text ({len(text)} chars)...")
        
        for i, section_raw in enumerate(raw_sections):
            # A. 清洗文本
            clean_section = clean_text(section_raw)
            if not clean_section: continue

            # B. 第二层切分：检查是否超长 (防 503)
            # 如果这一段还是很长，必须切碎处理
            sub_chunks = _smart_split_long_text(clean_section)
            
            section_audio = AudioSegment.empty()
            
            for chunk in sub_chunks:
                # 生成临时文件
                temp_filename = os.path.join(AUDIO_DIR, f"temp_{uuid.uuid4().hex}.mp3")
                success = await _generate_segment_file(chunk, voice, temp_filename)
                
                if success:
                    temp_files_to_cleanup.append(temp_filename)
                    # 读取并拼接到当前小节
                    chunk_audio = AudioSegment.from_mp3(temp_filename)
                    section_audio += chunk_audio
            
            # C. 将处理好的这一大节（Section）拼入最终音频
            final_audio += section_audio
            
            # D. 如果不是最后一节，且原文本里有分隔符，则插入静音
            # (注意：split后长度为N，则说明有N-1个分隔符)
            if i < len(raw_sections) - 1:
                print(f"   ☕ Inserting {PAUSE_DURATION_MS}ms pause...")
                final_audio += silence_audio

        # 4. 导出最终文件
        final_filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
        final_path = os.path.join(AUDIO_DIR, final_filename)
        
        final_audio.export(final_path, format="mp3")
        print(f"✅ Audio saved: {final_path}")
        
        # 5. 清理临时文件
        for f in temp_files_to_cleanup:
            if os.path.exists(f):
                os.remove(f)
                
        return final_path

    except Exception as e:
        print(f"❌ Audio generation error: {str(e)}")
        # 出错也要清理垃圾
        for f in temp_files_to_cleanup:
            if os.path.exists(f):
                os.remove(f)
        return None

if __name__ == "__main__":
    # 测试用例
    test_text = "Hola amigo. **Este es el texto limpio.** === Y aquí hay una pausa larga."
    asyncio.run(generate_audio_file(test_text, "es"))