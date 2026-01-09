import streamlit as st
import uuid
import tempfile
import os
import requests
import time
import sys
import warnings
from io import BytesIO
from requests.exceptions import ConnectionError, Timeout, RequestException

# ---------------------------------------------------------
# 配置区域
# ---------------------------------------------------------
API_URL = "http://localhost:8000/chat"
st.set_page_config(page_title="AI Knowledge Base", page_icon="🌱")

# ---------------------------------------------------------
# 工具函数
# ---------------------------------------------------------
def send_request_with_retry(url, payload, max_retries=3, timeout=120):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            if 500 <= response.status_code < 600:
                raise RequestException(f"Server Error {response.status_code}")
            return response
        except (ConnectionError, Timeout) as e:
            if attempt == max_retries - 1: raise e
            time.sleep(1)
            st.toast(f"⚠️ 网络波动，正在重试 ({attempt + 1}/{max_retries})...", icon="🔄")
        except RequestException as e:
            raise e

# ---------------------------------------------------------
# 文件解析逻辑 (Lazy Loading)
# ---------------------------------------------------------
def extract_text_from_epub(file_stream):
    try:
        from ebooklib import epub
        from bs4 import BeautifulSoup
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_file.write(file_stream.read())
            tmp_path = tmp_file.name
        book = epub.read_epub(tmp_path)
        chapters = []
        for item in book.get_items():
            if item.get_type() == epub.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                chapters.append(soup.get_text())
        os.remove(tmp_path)
        return "\n".join(chapters)
    except Exception as e:
        return f"Error reading EPUB: {e}"

def extract_text_from_txt(file_stream):
    try:
        return file_stream.read().decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_stream.read().decode("gbk")
        except:
            return "Error: Unsupported text encoding."

def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        pdf_file = BytesIO(pdf_bytes)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            old_stderr = sys.stderr
            with open(os.devnull, 'w') as devnull:
                try:
                    sys.stderr = devnull
                    reader = PdfReader(pdf_file, strict=False)
                    text = [page.extract_text() for page in reader.pages]
                    return "\n".join(text)
                finally:
                    sys.stderr = old_stderr
    except Exception as e:
        st.error(f"PDF 提取错误: {e}")
        return ""

def process_uploaded_file(uploaded_file):
    if not uploaded_file: return None
    file_type = uploaded_file.name.split('.')[-1].lower()
    if file_type == 'pdf':
        return extract_pdf_text(uploaded_file.read())
    elif file_type == 'epub':
        return extract_text_from_epub(uploaded_file)
    elif file_type == 'txt':
        return extract_text_from_txt(uploaded_file)
    return None

# ---------------------------------------------------------
# UI 渲染
# ---------------------------------------------------------
st.markdown("""
    <style>
    .gradient-text {
        background: linear-gradient(to right, #134e5e, #71b280, #134e5e);
        background-size: 200% auto;
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: shine 5s linear infinite;
        font-weight: bold;
    }
    .caption-gradient {
        background: linear-gradient(to right, #11998e, #38ef7d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.2em;
        font-style: italic;
    }
    @keyframes shine { to { background-position: 200% center; } }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
    .stFileUploader {
        background-color: white; padding: 15px; border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #ececec;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="gradient-text">Exocortex</h1>', unsafe_allow_html=True)
st.markdown('<p class="caption-gradient">I search, I decide, I execute. (Client Mode)</p>', unsafe_allow_html=True)

# --- 🔥 Session 初始化 (关键修复点 1) ---
if "messages" not in st.session_state: st.session_state.messages = []
if "thread_id" not in st.session_state: st.session_state.thread_id = str(uuid.uuid4())

# 新增：用于强制重置上传组件的 key
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0

# ---------------------------------------------------------
# 侧边栏逻辑
# ---------------------------------------------------------
with st.sidebar:
    st.markdown('<div style="font-size:1.2rem;font-weight:700;color:#2e7d32;margin-bottom:0.5rem;">🪵 Upload files</div>', unsafe_allow_html=True)
    
    # --- 🔥 文件上传组件 (关键修复点 2: 绑定动态 Key) ---
    # 当 uploader_key 改变时，Streamlit 会彻底重置这个组件，从而清空 UI 上的文件
    uploaded_files = st.file_uploader(
        "(PDF / EPUB / TXT)", 
        type=["pdf", "epub", "txt"],
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}"
    )
    
    if uploaded_files:
        current_file_names = sorted([f.name for f in uploaded_files])
        
        # 检查文件是否变化
        if st.session_state.get("current_file_list") != current_file_names:
            all_content = ""
            total_files = len(uploaded_files)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Parsing {file.name} ({i+1}/{total_files})...")
                content = process_uploaded_file(file)
                if content:
                    all_content += f"\n\n--- FILE START: {file.name} ---\n{content}\n--- FILE END: {file.name} ---\n"
                progress_bar.progress((i + 1) / total_files)
                
            if all_content:
                st.session_state["file_content"] = all_content
                st.session_state["current_file_list"] = current_file_names
                st.success(f"🌿 Loaded {total_files} files ({len(all_content)} chars)")
            else:
                st.error("No valid text extracted.")
            
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
        else:
            st.success(f"🍄 Ready: {len(uploaded_files)} files loaded")
    else:
        # 如果用户手动删除了所有文件，清理状态
        if "file_content" in st.session_state:
            del st.session_state["file_content"]
            del st.session_state["current_file_list"]

    st.divider()
    
    # --- 🔥 清除历史按钮 (关键修复点 3) ---
    if st.button("🥀 Clear History"):
        # 1. 清空聊天记录
        st.session_state.messages = []
        # 2. 生成新 Thread ID
        st.session_state.thread_id = str(uuid.uuid4())
        
        # 3. 彻底删除文件内容缓存
        if "file_content" in st.session_state: 
            del st.session_state["file_content"]
        if "current_file_list" in st.session_state: 
            del st.session_state["current_file_list"]
            
        # 4. 核心：改变 uploader_key，强制 UI 上的文件组件重置
        st.session_state.uploader_key += 1
        
        st.rerun()

# ---------------------------------------------------------
# 聊天历史回显
# ---------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio_url"): st.audio(msg["audio_url"])

# ---------------------------------------------------------
# 核心交互逻辑
# ---------------------------------------------------------
if prompt := st.chat_input("Enter a note or topic..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    final_query = prompt
    # 注入文件上下文
    if st.session_state.get("file_content"):
        context = st.session_state["file_content"][:30000] 
        final_query = f"【Context from uploaded files】:\n{context}\n\n【User Query】:\n{prompt}"

    payload = {"query": final_query, "thread_id": st.session_state.thread_id}

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.status("Thinking... (Connecting to Brain 🌻)", expanded=False) as status:
            try:
                status.write("🌵 Sending request...")
                response = send_request_with_retry(API_URL, payload)
                
                if response.status_code == 200:
                    data = response.json()
                    bot_text = data.get("text", "")
                    audio_url = data.get("audio_url")
                    notion_url = data.get("notion_url")

                    full_text = bot_text
                    if notion_url: full_text += f"\n\n[🔗 Notion Link]({notion_url})"
                    
                    status.update(label="Complete", state="complete", expanded=False)
                    message_placeholder.markdown(full_text)
                    if audio_url: st.audio(audio_url)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_text,
                        "audio_url": audio_url
                    })
                else:
                    status.update(label="Error", state="error")
                    message_placeholder.error(f"❌ Server Error: {response.text}")
            except Exception as e:
                status.update(label="Failed", state="error")
                message_placeholder.error(f"❌ Error: {str(e)}")