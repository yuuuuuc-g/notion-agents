import streamlit as st
import uuid
import warnings
import sys
import os
from agent_graph import run_agent
from pypdf import PdfReader
from io import BytesIO

st.set_page_config(page_title="ReAct Knowledge Agent", page_icon="⚡")

st.title("⚡ Autonomous ReAct Agent")
st.caption(" I search, I decide, I execute.")

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# PDF 文件上传
def extract_pdf_text(pdf_bytes: bytes) -> str:
    """从 PDF 字节数据中提取文本"""
    try:
        pdf_file = BytesIO(pdf_bytes)
        # 抑制 pypdf 的格式警告（PDF 文件格式不规范时的警告）
        # 这些警告是直接打印到 stderr 的，需要重定向
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            # 重定向 stderr 以抑制 pypdf 的格式警告输出
            with open(os.devnull, 'w') as devnull:
                old_stderr = sys.stderr
                sys.stderr = devnull
                try:
                    reader = PdfReader(pdf_file, strict=False)  # strict=False 允许更宽松的解析
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                finally:
                    sys.stderr = old_stderr
        return text
    except Exception as e:
        st.error(f"PDF 提取错误: {e}")
        return ""

uploaded_file = st.file_uploader("上传 PDF 文件（可选）", type=["pdf"])
pdf_text = None
if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    pdf_text = extract_pdf_text(pdf_bytes)

if prompt := st.chat_input("Enter a note or topic..."):
    # 1. 显示用户输入
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Agent 运行
    with st.chat_message("assistant"):
        print("PDF length:", len(pdf_text) if pdf_text else 0)
        with st.spinner("🤖 Agent is working (Searching -> Thinking -> Acting)..."):
            try:
                response = run_agent(prompt, pdf_text, st.session_state.thread_id)
                st.markdown(response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )
            except Exception as e:
                st.error(f"Error: {e}")