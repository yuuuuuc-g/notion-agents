"""
app.py
Streamlit Client
已修复: 适配后端流式输出 (Streaming) + 语音自动提取，同时保留原版 UI 渲染
"""

import streamlit as st
import uuid
import tempfile
import os
import requests
import time
import sys
import warnings
import re  # 🆕 新增：用于正则提取音频链接
from io import BytesIO
from requests.exceptions import ConnectionError, Timeout, RequestException

# ---------------------------------------------------------
# 配置区域
# ---------------------------------------------------------
API_URL = "http://localhost:8000/chat"
# 🔥 这里的密码必须和 .env 里的 API_SECRET 一致
CLIENT_API_SECRET = os.getenv("API_SECRET", "exocortex-default-secret-2026")

st.set_page_config(page_title="AI Knowledge Base", page_icon="🌱")


# ---------------------------------------------------------
# 工具函数
# ---------------------------------------------------------
# (保留此函数定义，虽然流式请求不再直接调用它，但保留以防其他非流式需求)
def send_request_with_retry(url, payload, max_retries=3, timeout=120):
    headers = {
        "Authorization": f"Bearer {CLIENT_API_SECRET}",
        "Content-Type": "application/json",
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout
            )
            if response.status_code == 401:
                st.error("🔒 鉴权失败：API Key 不正确，请检查 .env 配置。")
                raise RequestException("Unauthorized")
            if 500 <= response.status_code < 600:
                raise RequestException(f"Server Error {response.status_code}")
            return response
        except (ConnectionError, Timeout) as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)
            st.toast(
                f"⚠️ 网络波动，正在重试 ({attempt + 1}/{max_retries})...", icon="🔄"
            )
        except RequestException as e:
            raise e


# ---------------------------------------------------------
# 文件解析逻辑 (保持不变)
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
                soup = BeautifulSoup(item.get_content(), "html.parser")
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
        except UnicodeDecodeError:
            return "Error: Unsupported text encoding."


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        pdf_file = BytesIO(pdf_bytes)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            old_stderr = sys.stderr
            with open(os.devnull, "w") as devnull:
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
    if not uploaded_file:
        return None
    file_type = uploaded_file.name.split(".")[-1].lower()
    if file_type == "pdf":
        return extract_pdf_text(uploaded_file.read())
    elif file_type == "epub":
        return extract_text_from_epub(uploaded_file)
    elif file_type == "txt":
        return extract_text_from_txt(uploaded_file)
    return None


# ---------------------------------------------------------
# UI 渲染 (保持不变)
# ---------------------------------------------------------
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

st.markdown('<h1 class="gradient-text">Exocortex</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="caption-gradient">I search, I decide, I execute. (Client Mode)</p>',
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.2rem;font-weight:700;color:#2e7d32;margin-bottom:0.5rem;">🪵 Upload files</div>',
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "(PDF / EPUB / TXT)",
        type=["pdf", "epub", "txt"],
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
    )

    if uploaded_files:
        current_file_names = sorted([f.name for f in uploaded_files])
        if st.session_state.get("current_file_list") != current_file_names:
            all_content = ""
            total_files = len(uploaded_files)
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(uploaded_files):
                status_text.text(f"Parsing {file.name} ({i + 1}/{total_files})...")
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
        if "file_content" in st.session_state:
            del st.session_state["file_content"]
            del st.session_state["current_file_list"]

    st.divider()

    if st.button("🥀 Clear History"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        if "file_content" in st.session_state:
            del st.session_state["file_content"]
        if "current_file_list" in st.session_state:
            del st.session_state["current_file_list"]
        st.session_state.uploader_key += 1
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("audio_url"):
            st.audio(msg["audio_url"])

if prompt := st.chat_input("Enter a note or topic..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    final_query = prompt
    if st.session_state.get("file_content"):
        context = st.session_state["file_content"][:30000]
        final_query = (
            f"【Context from uploaded files】:\n{context}\n\n【User Query】:\n{prompt}"
        )

    payload = {"query": final_query, "thread_id": st.session_state.thread_id}

    # 构造 Header (Streamlit 客户端也需要鉴权)
    headers = {
        "Authorization": f"Bearer {CLIENT_API_SECRET}",
        "Content-Type": "application/json",
    }

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        # 保留原本的 Status UI，看起来更丝滑
        with st.status(
            "Thinking... (Connecting to Brain 🌻)", expanded=False
        ) as status:
            try:
                # 🔥 核心修改：使用 stream=True
                response = requests.post(
                    API_URL, json=payload, headers=headers, stream=True, timeout=120
                )

                if response.status_code == 200:
                    status.update(
                        label="Streaming...", state="complete", expanded=False
                    )
                    full_response = ""
                    audio_url = None

                    # 循环读取流
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            text_chunk = chunk.decode("utf-8")
                            full_response += text_chunk
                            # 打字机效果：加上光标
                            message_placeholder.markdown(full_response + "▌")

                            # 🔥 实时正则检测音频链接
                            # 匹配 Docker 内部路径: /app/generated_audio/audio_xxxx.mp3
                            match = re.search(
                                r"/app/generated_audio/(audio_[a-f0-9]+\.mp3)",
                                full_response,
                            )
                            if match:
                                filename = match.group(1)
                                # 转换为外部 localhost URL
                                audio_url = f"http://localhost:8000/audio/{filename}"

                    # 流结束，显示完整文本（去掉光标）
                    message_placeholder.markdown(full_response)

                    if audio_url:
                        st.audio(audio_url)

                    # 存入历史消息
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": full_response,
                            "audio_url": audio_url,
                        }
                    )
                else:
                    status.update(label="Error", state="error")
                    message_placeholder.error(f"❌ Server Error: {response.text}")

            except Exception as e:
                status.update(label="Failed", state="error")
                message_placeholder.error(f"❌ Connection Error: {str(e)}")
