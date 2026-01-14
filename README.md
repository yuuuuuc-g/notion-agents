# 🌱 Exocortex (Notion-Prism-React)

> **Enterprise-Grade Personal Cognitive OS.**
> 基于 **Next.js + FastAPI + LangGraph** 的生产级全栈智能体系统。

**Exocortex** 不是一个简单的聊天 Demo，它是一套**数据主权自控**的个人知识操作系统。
它采用 **Client-Server 架构**，结合 **领域驱动设计 (DDD)**，实现了从“瞬时交互”到“长期记忆”的完整闭环。

---

## 🏗️ 系统架构设计 (Architecture Blueprint)

系统严格遵循 **分层架构 (Layered Architecture)** 原则，各层职责边界清晰。

### 1. 接入层 (Presentation Layer)
* **🚀 User Interface (Next.js)**: 
    * 基于 **React 19** 构建的现代化 SPA。
    * **职责**: 处理高频交互（Chat）、流式渲染（Streaming）、文件拖拽。
    * **特性**: 零刷新、WebSocket/SSE 支持、CORS 直连后端。
* **🛠️ Admin Dashboard (Streamlit)**:
    * **职责**: 知识库可视化管理、向量索引调试、Prompt 迭代。
    * **特性**: 快速数据可视化，作为“系统后台”存在。

### 2. 核心逻辑层 (Application Core)
* **🧠 Brain Server (FastAPI)**: 
    * RESTful API 设计，通过 Pydantic 进行严格的数据校验。
    * **Async/Await**: 全链路异步处理，解决 Python 并发瓶颈。
* **⚙️ Agent Orchestrator (LangGraph)**:
    * 放弃线性脚本，采用 **图 (Graph)** 结构管理 Agent 状态。
    * 支持 **循环思考 (Loop)**、**自我修正 (Reflection)** 和 **多路径路由 (Routing)**。

### 3. 数据持久层 (Data Persistence) - "漏斗模型"
* **🔥 Hot (Redis)**: [Session/Cache]
    * 存储会话上下文、上传文件的临时内容、任务队列状态。
    * *Value*: 解决大文本重复传输问题，实现无状态 API。
* **🟡 Warm (SQLite)**: [Metadata]
    * 存储文档元数据 (Meta-store)、父子索引关联关系 (Parent-Child Map)。
* **🧊 Cold (ChromaDB + Notion)**: [Long-term]
    * **ChromaDB**: 存储语义向量 (Embeddings)，用于模糊检索。
    * **Notion**: 存储人类可读笔记，作为最终的知识归档地。

---

## 🛠️ 技术栈清单 (Tech Stack)

| 模块 | 技术选型 | 选型理由 |
| :--- | :--- | :--- |
| **Frontend** | **Next.js (React)** + Tailwind | 工业级交互体验，生态最强。 |
| **Backend** | **FastAPI** (Python 3.10+) | 高性能异步框架，原生支持 OpenAPI。 |
| **Orchestration** | **LangGraph** | 比 LangChain Chain 更灵活的状态机管理。 |
| **LLM Provider** | **OpenRouter** (DeepSeek/GPT4) | 聚合接口，低成本，高可用。 |
| **Embedding** | **SiliconFlow** (BGE-M3) | 国内直连，SOTA 级的中文向量效果。 |
| **Vector DB** | **ChromaDB** | 轻量级、本地化、易于 Docker 部署。 |
| **Cache** | **Redis** | (生产环境标准) 高速缓存与消息队列。 |
| **DevOps** | **Docker Compose** | 一键拉起全栈环境，环境隔离。 |

---

## 📂 领域驱动目录结构 (Directory Structure)

```text
exocortex/
├── web/                    # ⚛️ [Frontend] Next.js 项目
│   ├── src/components/     #    - UI 组件 (UploadZone, ChatBubble)
│   ├── src/services/       #    - API 请求封装
│   └── next.config.ts      #    - 路由配置
├── server/                 # 🧠 [Backend] 核心代码库
│   ├── api/                #    - 接口层 (Routes)
│   ├── core/               #    - 全局配置 (Config, Logging)
│   ├── domain/             #    - 领域逻辑 (DDD Core)
│   │   ├── agent/          #      - LangGraph 状态机
│   │   ├── notion/         #      - Notion 同步逻辑
│   │   └── vector/         #      - 向量检索逻辑
│   ├── infrastructure/     #    - 基础设施适配器
│   │   ├── cache/          #      - Redis 客户端封装
│   │   ├── llm/            #      - LLM Provider 封装
│   │   └── storage/        #      - SQLite/Chroma 封装
│   └── service/            #    - 应用服务 (业务流程编排)
├── docker/                 # 🐳 部署配置
├── server.py               # 🚀 启动入口
├── requirements.txt        # 📦 后端依赖
└── docker-compose.yml      # 🐙 全栈编排文件

```

---

## 🚀 生产环境启动 (Production Start)

### 前置要求

* Docker & Docker Compose
* OpenAI/OpenRouter API Key
* Notion Integration Token

### 一键启动

```bash
# 拉起 Redis, Chroma, FastAPI, Streamlit
docker compose up -d --build

# 进入 Next.js 开发模式 (独立启动以便热更)
cd web && npm run dev

# 查看后台日志
docker compose logs -f --tail=50 exocortex

```

---

## 🗺️ Roadmap (架构落地计划)

* [x] **Phase 1: 解耦** - 前后端分离，Docker 化。 ✅
* [ ] **Phase 2: 缓存** - 引入 Redis 替代内存字典，实现真正的无状态后端。
* [ ] **Phase 3: 异步** - 引入 BackgroundTasks，将 Notion 写入改为后台任务。
* [ ] **Phase 4: 记忆** - 完善 SQLite 父子索引，优化 RAG 召回率。

---

## 📜 License

MIT License.

```

---

### 👨‍🏫 架构师的执行建议 (Next Steps)

现在架构定型了，为了避免“踩坑”，我们接下来的开发顺序必须严格：

1.  **基础设施先行**：在 `docker-compose.yml` 里加上 **Redis**。不要怕麻烦，现在不加以后加更痛。
2.  **后端改造**：修改 `server.py`，引入 Redis 客户端。把之前的“全局字典”换成 Redis 操作。
3.  **前端对接**：前端 UI 不用大改，只需要对接新的 API 逻辑（传 ID 而不是传文本）。
