import asyncio
import edge_tts
import re
import tempfile
import os
from pydub import AudioSegment

# --- 声音配置 ---
VOICE_MAP = {
    "es": "es-MX-DaliaNeural",  # 西班牙语
    "en": "en-US-AriaNeural",   # 英语
    "zh": "zh-CN-XiaoxiaoNeural"
}
RATE = "-10%" 
PAUSE_DURATION_MS = 1000 
PAUSE_MARKER = "==="

def clean_text_for_audio(text):
    if not text: return ""
    text = re.sub(r"[\*\#]", "", text) 
    text = re.sub(r"\-{2,}", "", text) 
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text) 
    return text.strip()

async def _generate_audio_async(text_content, output_path, language="es"):
    voice = VOICE_MAP.get(language, VOICE_MAP["es"])
    segments_text = text_content.split(PAUSE_MARKER)
    
    final_audio = AudioSegment.empty()
    silence_audio = AudioSegment.silent(duration=PAUSE_DURATION_MS)
    
    # 使用临时目录，避免权限问题
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        temp_filename = tmp.name

    try:
        # 🔍 打印日志，确认正在处理
        print(f"🎤 Generating audio for: {text_content[:20]}...")
        
        has_content = False
        for i, segment in enumerate(segments_text):
            clean_segment = clean_text_for_audio(segment)
            if not clean_segment: continue
            
            communicate = edge_tts.Communicate(clean_segment, voice, rate=RATE)
            await communicate.save(temp_filename)
            
            # 🛑 关键修复：检查生成的文件是不是空的
            if os.path.getsize(temp_filename) == 0:
                print("⚠️ Warning: Generated segment is empty, skipping.")
                continue
                
            segment_audio = AudioSegment.from_mp3(temp_filename)
            final_audio += segment_audio
            if i < len(segments_text) - 1:
                final_audio += silence_audio
            
            has_content = True
            
        if has_content:
            final_audio.export(output_path, format="mp3")
            print(f"✅ Audio saved to {output_path} (Size: {os.path.getsize(output_path)} bytes)")
            return True
        else:
            print("❌ No valid audio content generated.")
            return False

    except Exception as e:
        print(f"❌ Audio generation error: {e}")
        return False
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def generate_audio_file(text, language="es"):
    output_dir = "generated_audio"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = f"audio_{os.getpid()}_{hash(text[:20])}.mp3"
    output_path = os.path.join(output_dir, filename)
    abs_path = os.path.abspath(output_path)
    
    try:
        # 运行异步任务
        asyncio.run(_generate_audio_async(text, abs_path, language))
        # 二次确认文件真的存在且不为空
        if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
            return abs_path
        return None
    except Exception as e:
        print(f"Failed to run async audio gen: {e}")
        return None