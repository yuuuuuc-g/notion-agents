import asyncio
import edge_tts
import re
import tempfile
import os
import uuid
from pydub import AudioSegment

# --- 声音配置 ---
VOICE_MAP = {
    "es": "es-MX-DaliaNeural",  
    "en": "en-US-AriaNeural",   
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
    
    # 创建一个临时文件路径，不立即打开，避免占用
    # 使用 delete=False 让我们可以手动管理它的生命周期
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        temp_filename = tmp.name

    try:
        # 🔍 打印日志
        print(f"🎤 Generating audio for: {text_content[:20]}...")
        
        has_content = False
        for i, segment in enumerate(segments_text):
            clean_segment = clean_text_for_audio(segment)
            if not clean_segment: continue
            
            # 覆盖写入同一个临时文件
            communicate = edge_tts.Communicate(clean_segment, voice, rate=RATE)
            await communicate.save(temp_filename)
            
            # 检查文件大小
            if os.path.getsize(temp_filename) == 0:
                print("⚠️ Warning: Generated segment is empty, skipping.")
                continue
                
            # 读取音频片段
            segment_audio = AudioSegment.from_mp3(temp_filename)
            final_audio += segment_audio
            
            # 只要不是最后一段，就加停顿
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
        # 清理临时文件
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass

def generate_audio_file(text, language="es"):
    output_dir = "generated_audio"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
    
    output_path = os.path.join(output_dir, filename)
    abs_path = os.path.abspath(output_path)
    
    try:
        asyncio.run(_generate_audio_async(text, abs_path, language))
        
        if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
            return abs_path
        return None
    except Exception as e:
        print(f"Failed to run async audio gen: {e}")
        return None