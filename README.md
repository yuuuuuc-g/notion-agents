# 🌱 Exocortex (Notion-Prism-React)

> **你的个人认知外延系统 (Your Personal Cognitive Extension)。**
> 基于 **Client-Server 架构** 的多模态智能 Agent，集成 "大脑外延" 知识管理与 "AI 语音助教"。

**Exocortex** 是一个经过深度工程化重构的自动化系统。它采用了现代化的 **前后端分离** 与 **领域驱动设计 (DDD)**：后端 (**FastAPI**) 作为“大脑”负责逻辑思考与工具调用，前端 (**Streamlit**) 作为“皮肤”负责交互与展示。

它采用 **混合云 AI 架构 (Hybrid Cloud AI Stack)**，通过 **OpenRouter** 连接顶级大模型进行思考，通过 **SiliconFlow (硅基流动)** 进行高性能向量化，告别了沉重的本地模型依赖，实现了**云原生、低延迟、高稳定性**的运行体验。

---

## ✨ 核心特性

### 🏗️ 工业级分层架构 (Decoupled & Modular)

* **Client-Server 分离**：
    * **🧠 Server (FastAPI)**：独立运行的后端服务。负责 LangGraph 状态流转、Notion 写入、音频生成及向量检索。即便前端关闭，大脑依然在线。
    * **💻 Client (Streamlit)**：极简的“瘦客户端”。只负责发送 HTTP 请求和播放媒体，彻底解决了 Streamlit 刷新导致上下文丢失与内存泄漏的问题。
* **模块化领域设计**：告别扁平脚本，采用 `config`, `agent`, `vector` 等独立模块，职责边界清晰，维护成本极低。

### 🧠 Level-Chunk 高级检索 (Context-Aware RAG) [NEW]

* **父子索引策略 (Parent-Child Indexing)**：
    * **Child (Vector)**：将文档切碎为小片段存入 ChromaDB，实现精准的语义匹配。
    * **Parent (Storage)**：将完整文档存入 SQLite (`doc_store.db`)。
    * **Retrieval**：搜索时命中“细节”，返回时自动回溯“全貌”，确保 AI 回答具备完整的上下文背景。

### ☁️ 云原生与极致轻量

* **Docker 容器化**：提供标准 `Dockerfile` 与 `docker-compose`，支持一键拉起整套环境，无需配置本地 Python 依赖，开箱即用。
* **零本地模型负担**：移除 `torch`、`transformers` 等 GB 级依赖，安装包体积缩减 90%。
* **双脑协同**：
    * **思考 (Chat)**：集成 **OpenRouter (DeepSeek/GPT-4o)**，低成本获取顶级推理能力。
    * **记忆 (Embedding)**：集成 **SiliconFlow (BAAI/bge-m3)**，利用国内直连的高性能 Embedding 服务。

### 🤖 双轨智能决策 (ReAct & Graph)

* **Graph 编排器**：基于 **LangGraph** 状态机，Agent 拥有清晰的思考路径（State Management）。
* **Agent 路由**：后端根据意图自动分流：
    * 🟢 **音频快车道**：跳过 RAG，直接调用 TTS 工具，极速响应。
    * 🔵 **知识慢车道**：执行深度检索、去重、Notion 写入与 ChromaDB 同步。

---

## 🏗️ 系统架构

### 📂 项目结构 (Directory Structure)

```text
exocortex/
├── config/               # ⚙️ Config: 统一管理 Env 与全局常量
│   └── settings.py       
├── agent/                # 🧠 Agent: 大脑皮层
│   ├── agent_graph.py    #    - 思考路径 (LangGraph)
│   └── prompts.py        #    - 提示词管理 (SOP & Identity)
├── audio/                # 🔊 Domain: 音频服务
│   └── audio_ops.py      #    - TTS 生成与切片逻辑
├── notion/               # 📝 Domain: 知识库服务
│   ├── block_builder.py  #    - 排版工 (Markdown -> Blocks)
│   └── notion_ops.py     #    - 快递员 (Notion API CRUD)
├── vector/               # 💾 Domain: 向量记忆 (Level-Chunk Core)
│   ├── embedding_provider.py # - 适配器 (SiliconFlow fix)
│   ├── vector_store.py   #    - 索引管理 (ChromaDB + Parent ID Logic)
│   ├── doc_store.py      #    - [NEW] 父文档存储 (SQLite)
│   └── splitter.py       #    - [NEW] 智能切分器
├── llm/                  # 🤖 Provider: 模型工厂
│   └── llm_provider.py   
├── tools/                # 🛠️ Tools: 外部工具定义 (LangChain)
├── server.py             # 🚪 Entry: 后端入口 (FastAPI)
├── app.py                # 💻 Entry: 前端入口 (Streamlit)
├── docker-compose.yml    # 🐳 Docker: 容器编排
├── Dockerfile            # 🐳 Docker: 镜像构建
├── start.sh              # 🚀 Script: 本地一键启动
├── requirements.txt      # 📦 Deps: 依赖清单
└── .env                  # 🔐 Secrets: 密钥文件

```

### 🔄 架构演进 (Evolution)

* **Phase 1 (Script)**: 原始阶段。单一 Python 脚本，采用硬编码的线性逻辑。
* **Phase 2 (Graph Workflow)**: **逻辑升级**。引入 **LangGraph** 编排器，工作流可视化。
* **Phase 3 (Client-Server)**: **服务化**。彻底分离 FastAPI 后端与 Streamlit 前端。
* **Phase 4 (Modular Refactor)**: **工程化**。引入 DDD (领域驱动设计) 与配置中心。
* **Phase 5 (Cognitive Depth & Container)**: **深度进化**。引入 Level-Chunk 索引策略（见树木亦见森林）与 Docker 容器化部署。

---

## 🚀 快速开始

### 方式 A：Docker 容器化启动 (推荐) 🐳

最稳定、最干净的运行方式。

```bash
# 1. 启动服务 (后台运行)
docker compose up -d

# 2. 访问
# 前端: http://localhost:8501
# API 文档: http://localhost:8000/docs

# 3. 停止服务
docker compose down

```

### 方式 B：本地 Python 启动

适用于调试或开发。

1. **安装依赖**
```bash
pip install -r requirements.txt
# 注意：本地运行需手动安装 FFmpeg (macOS: brew install ffmpeg)

```


2. **配置环境变量**
复制 `.env.example` 为 `.env` 并填入 Key。
3. **启动脚本**
```bash
chmod +x start.sh
./start.sh

```



---

## 📖 使用指南

### 1. 语言学习 (Text-to-Speech)

> **User**: "把这句话转成西班牙语：La vida es sueño."
> **Flow**: Client -> API -> Graph (Router) -> TTS Tool -> 生成 MP3 -> 返回 URL -> Client 播放。

### 2. 知识库构建 (RAG)

> **User**: "把这篇关于 Transformer 的笔记存入 Notion。"
> **Flow**: Client -> API -> Graph (Planner) -> DocStore (Save Parent) -> Chroma (Save Child) -> Notion API。

### 3. 历史回溯 (Context Retrieval)

> **User**: "我上周关于委内瑞拉局势的分析，核心观点是什么？"
> **Flow**: Client -> API -> Vector Search (Hit Child Chunk) -> **Fetch Parent (SQLite)** -> LLM Summarize -> Answer。

---

## 🔧 未来规划 (Roadmap)

* [x] **架构解耦**：完成 FastAPI 与 Streamlit 的分离。✅
* [x] **代码模块化**：完成核心逻辑的 DDD 重构。✅
* [x] **向量服务迁移**：从不稳定的 OpenRouter 迁移至高性能 SiliconFlow。✅
* [x] **高级检索增强 (Advanced RAG)**：实现 Level-Chunk (父子索引) 策略。✅
* [x] **Docker 化**：实现一键容器化部署。✅
* [ ] **语音输入 (STT)**：集成 OpenAI Whisper / Groq，给 Exocortex 加上“耳朵”。
* [ ] **MCP 深度集成**：完善 `mcp_server.py`，支持 IDE 直接调用知识库。

---

## 📜 License

MIT License.