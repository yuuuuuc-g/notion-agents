import streamlit as st
import uuid
import warnings
import sys
import os
import tempfile
from ebooklib import epub
from bs4 import BeautifulSoup
from agent_graph import run_agent
from pypdf import PdfReader
from io import BytesIO


st.set_page_config(page_title="ReAct Knowledge Agent", page_icon="🌱")

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
st.markdown('<h1 class="gradient-text">  Yuc\'s Notion Agent</h1>', unsafe_allow_html=True)
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

# 文件上传
def extract_text_from_epub(file_stream):
    """解析 EPUB 文件内容"""
    try:
        # EbookLib 需要文件路径，所以先保存为临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_file.write(file_stream.read())
            tmp_path = tmp_file.name

        book = epub.read_epub(tmp_path)
        chapters = []
        
        # 遍历书籍内容，提取文本
        for item in book.get_items():
            if item.get_type() == epub.ITEM_DOCUMENT:
                # 使用 BeautifulSoup 去除 HTML 标签
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                chapters.append(soup.get_text())
        
        # 清理临时文件
        os.remove(tmp_path)
        
        return "\n".join(chapters)
    except Exception as e:
        return f"Error reading EPUB: {e}"

def extract_text_from_txt(file_stream):
    """解析 TXT 文件内容"""
    try:
        # 尝试 UTF-8 解码
        return file_stream.read().decode("utf-8")
    except UnicodeDecodeError:
        # 如果失败，尝试 gbk (兼容中文旧文件)
        try:
            return file_stream.read().decode("gbk")
        except:
            return "Error: Unsupported text encoding."
        
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
    
def process_uploaded_file(uploaded_file):
    """根据文件后缀分发处理逻辑"""
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    if file_type == 'pdf':
        return extract_pdf_text(uploaded_file.read())
    elif file_type == 'epub':
        return extract_text_from_epub(uploaded_file)
    elif file_type == 'txt':
        return extract_text_from_txt(uploaded_file)
    else:
        return None

with st.sidebar:
    # 注入自定义 CSS 样式
    st.markdown("""
    <style>
    /* 修改侧边栏整体背景色 */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* 美化 Upload File 标题 */
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #2e7d32; /* 森林绿 */
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* 给上传组件加一个精致的卡片外框 */
    .stFileUploader {
        background-color: white;
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #ececec;
    }

    /* 隐藏原生的 "Drag and drop file here" 标签，让界面更干净 */
    .st-emotion-cache-1ae8k9d {
        color: #666;
    }
    </style>
    """, unsafe_allow_html=True)
    # 使用带有自定义样式的标题
    st.markdown('<div class="sidebar-header"> 🪵 Upload file</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "(PDF / EPUB / TXT)", 
        type=["pdf", "epub", "txt"],
        help="支持上传 PDF、电子书或纯文本文件供 Agent 学习"
    )
    
    # 清空按钮，方便重置对话
    if st.button("🥀 "):
        st.session_state.messages = []
        st.rerun()
        
file_content = None 
if uploaded_file is not None:
    # 调用刚才写的统一处理函数
    file_content = process_uploaded_file(uploaded_file)
    
    if file_content:
        st.sidebar.success(f"已加载: {uploaded_file.name} ({len(file_content)} 字符)")
    else:
        st.sidebar.error("无法读取文件内容")

if prompt := st.chat_input("Enter a note or topic..."):
    # 1. 显示用户输入
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Agent 运行
    with st.chat_message("assistant"):
        print("file length:", len(file_content) if file_content else 0)
        with st.spinner("🤖 Agent is working (Searching -> Thinking -> Acting)..."):
            try:
                response = run_agent(prompt, file_content, st.session_state.thread_id)
                st.markdown(response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )
            except Exception as e:
                st.error(f"Error: {e}")