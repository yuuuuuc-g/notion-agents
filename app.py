import streamlit as st
import uuid
import warnings
import sys
import os
from agent_graph import run_agent
from pypdf import PdfReader
from io import BytesIO

st.set_page_config(page_title="ReAct Knowledge Agent", page_icon="⚡")

# 定义 CSS 动画样式
# ---------------------------------------------------------
# ✨ UI 标题配置 
# ---------------------------------------------------------
st.markdown("""
    <style>
    /* 定义xxx色流动动画 */
    .gradient-text {
        /* 这里改了颜色：从 嫩绿(#a8ff78) 到 薄荷青(#78ffd6) 再回到 嫩绿 */
        background: linear-gradient(to right, #134e5e, #71b280, #134e5e);
        background-size: 200% auto;
        
        /* 裁剪背景到文字 */
        color: #000;
        background-clip: text;
        text-fill-color: transparent;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        
        /* 动画设置 */
        animation: shine 5s linear infinite;
        font-weight: bold;
    }
    
    /* 副标题样式 (保持淡雅的青灰色) */
    .caption-gradient {
        background: linear-gradient(to right, #11998e, #38ef7d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.2em;
        font-style: italic;
    }

    /* 动画关键帧 */
    @keyframes shine {
        to {
            background-position: 200% center;
        }
    }
    </style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="gradient-text">🌱  Yuc\'s Notion Agent</h1>', unsafe_allow_html=True)
st.markdown('<p class="caption-gradient">I search, I decide, I execute.</p>', unsafe_allow_html=True)

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

with st.sidebar:
    st.header("🪵 upload file")  # 加个标题更好看
    uploaded_file = st.file_uploader("", type=["pdf"])
    
    # 增加一个清空按钮，方便重置对话
    if st.button("🥀 "):
        st.session_state.messages = []
        st.rerun()
pdf_text = None
if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    pdf_text = extract_pdf_text(pdf_bytes)
    st.sidebar.success(f"已加载: {uploaded_file.name}")

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