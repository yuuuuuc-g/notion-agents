---

```markdown
# 🧠 Exocortex (Notion-Prism-React)

> **你的个人认知外延系统 (Your Personal Cognitive Extension)。**
> 集成 "第二大脑" 知识管理与 "AI 语音助教" 的多模态智能 Agent。

**Exocortex** 是一个基于 LangGraph ReAct 架构的自动化系统。它不仅仅是一个笔记工具，更是一个能听、能写、能思考的数字助理。它既能将复杂的 PDF/文本转化为结构化的 Notion 知识库，也能利用微软 Edge TTS 技术辅助你的语言学习（西班牙语/英语）。

---

## ✨ 核心特性

### 🎧 多模态音频生成 (New)
- **AI 语音助教**：集成 `edge-tts`，支持将任意文本转化为自然流畅的语音。
- **智能语种检测**：自动识别并支持 **西班牙语 (Default)** 和 **英语** 发音，专为语言学习者打造。
- **即时播放与下载**：生成的音频直接嵌入聊天界面播放，并提供 MP3 下载，自动处理文件路径传输。

### 🧠 双轨智能决策 (Dual-Path Logic)
- **高效分流**：Agent 内置任务分类器：
  - 🟢 **音频任务**：走“快车道”，**跳过向量检索**，直接调用 TTS 工具，快速响应。
  - 🔵 **知识任务**：走“慢车道”，执行深度检索与逻辑去重。
- **LangGraph 驱动**：基于 ReAct 模式，拥有独立的思考、工具调用与参数修正能力。

### 🔍 语义去重与融合
- **知识完备性检查**：在写入知识库前，Agent 始终先搜索向量库（ChromaDB）。
- **智能合并 (Merge)**：若发现相似笔记，自动读取旧内容并与新知融合，拒绝碎片化冗余。

### 🛠️ 强大的工程化实现
- **Notion 深度集成**：自动处理 Markdown 转 Blocks，支持 **分片写入** (完美解决 Notion API 100 block 限制)。
- **File 全流程支持**：UI 上传 -> 解析 -> `Session State` 持久化 -> 注入上下文。
- **Write-Through 策略**：Notion 写入成功后立即同步向量索引，确保“大脑”与“笔记本”实时一致。

---

## 🏗️ 系统架构

### 📂 项目结构

```text
exocortex/
├── app.py                # 🖥️ Streamlit UI：负责聊天、音频播放、文件状态管理
├── agent_graph.py        # 🧠 Brain：定义 SOP、双轨决策逻辑与 Graph 初始化
├── tools.py              # 🛠️ Tools：工具箱 (Notion管理 / 语音生成 / 向量检索)
├── audio_ops.py          # 🔊 Ops：音频生成核心 (Edge-TTS / Pydub / 正则清洗) 
├── notion_ops.py         # 🧱 Ops：Notion API 底层封装
├── vector_ops.py         # 💾 Ops：向量数据库操作
├── llm_core.py           # 🔌 Core：LLM 配置
├── packages.txt          # 📦 环境配置：用于 Streamlit Cloud 安装 ffmpeg
├── requirements.txt      # 📦 Python 依赖
└── README.md

```

### 🔄 工作流 (Workflow)

```mermaid
graph TD
    User[用户输入 (文本/文件)] --> Classifier{⚡ 任务分类}
    
    subgraph "Path A: Audio (Fast Track)"
        Classifier -- 🔊 转语音/朗读 --> TTS[调用 convert_text_to_audio]
        TTS --> AudioFile[生成 MP3]
        AudioFile --> Player[前端显示播放器]
    end

    subgraph "Path B: Knowledge (Deep Think)"
        Classifier -- 📝 存笔记/整理 --> Search{🔍 向量搜索}
        Search -- 发现相似 --> Merge[⚗️ 决策: 合并内容]
        Search -- 无重复 --> Create[📝 决策: 新建页面]
        Merge & Create --> Write[Notion API]
        Write --> Sync[💾 同步至 Vector DB]
        Sync --> Link[✅ 返回 Notion 链接]
    end

```

---

## 🚀 快速开始

### 1. 安装依赖

需安装 Python 依赖及系统级音频处理库 `ffmpeg`。

```bash
# 1. Python 库
pip install -r requirements.txt

# 2. FFmpeg (本地运行需安装，Streamlit Cloud 会自动读取 packages.txt)
# macOS: brew install ffmpeg
# Windows: winget install ffmpeg

```

### 2. 配置环境变量 (.env)

```ini
OPENAI_API_KEY=sk-xxxx
NOTION_TOKEN=secret_xxxx
NOTION_DATABASE_ID=xxxx

```

### 3. 启动应用

```bash
streamlit run app.py

```

---

## 📖 使用指南

### 1.  语言学习模式 (Text-to-Speech)

直接告诉 Agent：

> "把下面这段话转成西班牙语/英语/中文语音：xxxx..."
> "Read this text for me."

**结果**：Agent 会跳过检索，直接在界面生成音频播放器。

### 2.  知识管理模式 (Knowledge Base)

输入笔记或上传文件：

> "整理这份 文件 的核心观点并写入 Notion。"
> "新建一个关于 'Transformer 架构' 的笔记。"

**结果**：Agent 会先去 Notion 查重，然后决定是新建还是合并，最后返回链接。

### 3. 📂 文件处理

在侧边栏上传 PDF/EPUB/TXT。上传后，文件内容会被锁定在 `Session State` 中，即使对话刷新也不会丢失，Agent 可随时读取。

---

## 🧠 Agent 行为规范 (SOP)

Agent 遵循严格的 **标准作业程序 (SOP)**：

1. **PRIME DIRECTIVE (最高指令)**：
* 如果是音频请求 -> **绝对禁止**搜索向量库 (节约时间/Token)。
* 如果是笔记请求 -> **必须**搜索向量库 (防止重复)。


2. **Output Protocol**：
* 音频任务必须返回 `File path: /path/to/file.mp3` 以触发前端播放器。
* 笔记任务仅返回 Notion 链接。



---

## 🛡️ 工程鲁棒性 (Robustness)

* ✅ **Session State 保持**：修复了 Streamlit 刷新导致上传文件上下文丢失的问题。
* ✅ **正则路径提取**：使用 Regex 从 Agent 的“废话”中精准提取 `.mp3` 路径，确保播放器稳定加载。
* ✅ **空文件防御**：在 `audio_ops` 中增加了文件大小检测，防止生成 0kb 的损坏音频。
* ✅ **Notion 分片**：自动处理长文写入限制。

---


## 📜 License

MIT License.
Designed for personal knowledge management and learning purposes.

```

```
