import asyncio
import edge_tts
import re
import os
import uuid # 引入 uuid 防止文件名冲突

# --- 声音配置 ---
VOICE_MAP = {
    "es": "es-MX-DaliaNeural",  # 西班牙语
    "en": "en-US-AriaNeural",   # 英语
    "zh": "zh-CN-XiaoxiaoNeural"
}
RATE = "-10%" 
# PAUSE_DURATION_MS 和 PAUSE_MARKER 在没有 pydub 时暂时失效，故不再使用

def clean_text_for_audio(text):
    if not text: return ""
    text = re.sub(r"[\*\#]", "", text) 
    text = re.sub(r"\-{2,}", "", text) 
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text) 
    return text.strip()

async def _generate_audio_async(text_content, output_path, language="es"):
    voice = VOICE_MAP.get(language, VOICE_MAP["es"])
    
    # 1. 清理文本
    clean_content = clean_text_for_audio(text_content)
    if not clean_content:
        print("❌ Warning: Text is empty after cleaning.")
        return False

    try:
        # 🔍 打印日志
        print(f"🎤 Generating audio for: {clean_content[:20]}...")
        
        # 2. 直接调用 EdgeTTS 生成 (不再分段拼接，以摆脱 pydub 依赖)
        communicate = edge_tts.Communicate(clean_content, voice, rate=RATE)
        await communicate.save(output_path)
            
        # 3. 检查生成结果
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"✅ Audio saved to {output_path} (Size: {os.path.getsize(output_path)} bytes)")
            return True
        else:
            print("❌ File created but is empty.")
            return False

    except Exception as e:
        print(f"❌ Audio generation error: {e}")
        return False

def generate_audio_file(text, language="es"):
    output_dir = "generated_audio"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 使用 uuid 替代 hash，防止负数和冲突
    filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
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