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

### ☁️ 云原生与极致轻量

* **零本地模型负担**：移除 `torch`、`transformers` 等 GB 级依赖，安装包体积缩减 90%，Streamlit 内存占用极低。
* **🧠 双脑协同**：
* **思考 (Chat)**：集成 **OpenRouter (DeepSeek/GPT-4o)**，低成本获取顶级推理能力。
* **记忆 (Embedding)**：集成 **SiliconFlow (BAAI/bge-m3)**，利用国内直连的高性能 Embedding 服务，彻底解决向量检索的稳定性与维度兼容问题。



### 🤖 双轨智能决策 (ReAct & Graph)

* **Graph 编排器**：基于 **LangGraph** 状态机，Agent 拥有清晰的思考路径（State Management），支持循环推理、错误修正和多步工具调用。
* **Agent 路由**：后端根据意图自动分流：
* 🟢 **音频快车道**：跳过 RAG，直接调用 TTS 工具，极速响应。
* 🔵 **知识慢车道**：执行深度检索、去重、Notion 写入与 ChromaDB 同步。



### 🎧 智能语音助教

* **Edge-TTS 集成**：支持西班牙语、英语、中文的高质量语音合成。
* **静态资源服务**：后端内置静态文件服务器，通过 URL 稳定分发音频，完美解决多轮对话中的文件访问冲突。

---

## 🏗️ 系统架构

### 📂 项目结构 (Directory Structure)

```text
exocortex/
├── config/               # ⚙️ Config: 财务部 (统一管理 Env 与全局常量)
│   └── settings.py       
├── agent/                # 🧠 Agent: 大脑皮层
│   ├── agent_graph.py    #    - 思考路径 (LangGraph)
│   └── prompts.py        #    - 提示词管理 (SOP & Identity)
├── audio/                # 🔊 Domain: 音频服务
│   └── audio_ops.py      #    - TTS 生成与切片逻辑
├── notion/               # 📝 Domain: 知识库服务
│   ├── block_builder.py  #    - 排版工 (Markdown -> Blocks)
│   └── notion_ops.py     #    - 快递员 (Notion API CRUD)
├── vector/               # 💾 Domain: 向量记忆
│   ├── embedding_provider.py # - 适配器 (SiliconFlow fix)
│   └── vector_store.py   #    - 仓库管理 (ChromaDB Ops)
├── llm/                  # 🤖 Provider: 模型工厂
│   └── llm_provider.py   
├── tools/                # 🛠️ Tools: 外部工具定义 (LangChain)
├── server.py             # 🚪 Entry: 后端入口 (FastAPI)
├── app.py                # 💻 Entry: 前端入口 (Streamlit)
├── start.sh              # 🚀 Script: 一键启动
├── requirements.txt      # 📦 Deps: 依赖清单
└── .env                  # 🔐 Secrets: 密钥文件

```

### 🔄 架构演进 (Evolution)

* **Phase 1 (Script)**: 原始阶段。单一 Python 脚本，采用硬编码的线性逻辑，功能单一。
* **Phase 2 (Graph Workflow)**: **逻辑升级**。引入 **LangGraph** 编排器，将程序重构为基于 **节点 (Nodes)** 和 **边 (Edges)** 的工作流模式。
* **Phase 3 (Client-Server)**: **服务化**。彻底分离 FastAPI 后端与 Streamlit 前端，解决状态丢失问题。
* **Phase 4 (Modular Refactor)**: **工程化**。引入 **DDD (领域驱动设计)** 思想，将扁平代码重构为高内聚、低耦合的模块化架构，实现了配置中心化与逻辑分层。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装轻量级依赖 (FastAPI, Streamlit, LangChain, ChromaDB 等)
pip install -r requirements.txt

# 安装 FFmpeg (音频处理必需)
# macOS: brew install ffmpeg

```

### 2. 配置环境变量 (.env)

请复制 `.env.example` 为 `.env` 并填入以下关键配置：

```ini
# 1. 思考大脑 (OpenRouter / DeepSeek)
OPENAI_API_KEY=sk-or-v1-xxxxxxxx
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# 2. 记忆向量 (SiliconFlow - BGE-M3)
SILICON_KEY=sk-xxxxxxxx  # 必填：用于向量化服务
SILICON_BASE_URL=https://api.siliconflow.cn/v1

# 3. Notion 知识库
NOTION_TOKEN=secret_xxxx
NOTION_DATABASE_ID=xxxx

```

### 3. 一键启动 🚀

无需分别运行两个终端，直接使用启动脚本：

```bash
# 赋予执行权限 (仅第一次)
chmod +x start.sh

# 启动 (自动后台运行 Server 并打开 Client)
./start.sh

```

---

## 📖 使用指南

### 1. 语言学习 (Text-to-Speech)

> **User**: "把这句话转成西班牙语：La vida es sueño."
> **Flow**: Client -> API -> Graph (Router) -> TTS Tool -> 生成 MP3 -> 返回 URL -> Client 播放。

### 2. 知识库构建 (RAG)

> **User**: "把这篇关于 Transformer 的笔记存入 Notion。"
> **Flow**: Client -> API -> Graph (Planner) -> Vector Ops -> Notion API -> 返回链接。

### 3. 历史回溯 (Memory Retrieval)

> **User**: "查询数据库：上周五我记录了什么关于 Exocortex 的内容？"
> **Flow**: Client -> API -> Embedding (SiliconFlow) -> ChromaDB Search -> LLM Answer。

---

## 🛡️ 工程鲁棒性 (Robustness)

* ✅ **配置中心化**：通过 `config/settings.py` 统一管理环境变量与全局常量，杜绝了分散读取导致的配置不一致风险。
* ✅ **维度熔断保护**：在 `vector/embedding_provider.py` 中实现了自动维度检查，防止 API 返回一维数组导致 ChromaDB 崩溃。
* ✅ **状态隔离**：前端刷新网页不再影响后端正在执行的长任务。
* ✅ **静态资源服务**：FastAPI 内置 Static Files 挂载，确保生成的音频文件可以通过 URL 稳定访问。

---

## 🔧 未来规划 (Roadmap)

* [x] **架构解耦**：完成 FastAPI 与 Streamlit 的分离。✅
* [x] **代码模块化**：完成核心逻辑的 DDD 重构。✅
* [x] **向量服务迁移**：从不稳定的 OpenRouter 迁移至高性能 SiliconFlow。✅
* [ ] **高级检索增强 (Advanced RAG)**：实现 **Level-Chunk (父子索引)** 策略。
* [ ] **MCP 深度集成**：完善 `mcp_server.py`，支持更多 Notion 操作，让 Exocortex 成为 IDE 的得力助手。
* [ ] **Docker 化**：提供 `Dockerfile` 和 `docker-compose.yml`，实现一键容器化部署。

---

## 📜 License

MIT License.