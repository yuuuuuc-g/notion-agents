# 🌱 BioBrain (Reborn v4.0)

Enterprise-Grade Personal Cognitive OS. 基于 FastAPI + LangGraph + Dependency Injection 的生产级、高可用 AI 后端系统。BioBrain 是一套数据主权自控的个人知识操作系统后端。经过 v4.0 深度重构，它从一个简单的脚本项目进化为采用 **整洁架构 (Clean Architecture)**、支持 **流式处理** 和 **全链路监控** 的工业级微服务。它实现了从“瞬时交互”到“长期记忆”的完整闭环。

## 🌟 项目概览 (Project Overview)

本项目是一个全栈应用，结合了强大的 **Python FastAPI** 后端和现代化的 **Next.js React** 前端。后端系统 **BioBrain** 提供了一个企业级的个人认知操作系统，专注于数据主权自控和高效的 AI 逻辑编排。前端则提供直观的用户界面，与后端无缝交互。

## ✨ 主要特性 (Key Features)

-   **企业级AI后端**: 基于 FastAPI 和 LangGraph，支持流式处理、高可用和全链路监控。
-   **整洁架构**: 严格遵循分层架构和依赖注入原则，实现模块化和高解耦。
-   **数据主权自控**: 个人知识操作系统后端，强调用户数据的自主管理。
-   **智能知识管理**: Notion 增量同步、Qdrant 语义向量存储。
-   **多模态处理**: 支持文件流式上传、PDF/EPUB 解析、TTS 语音合成。
-   **高性能**: 流式上传、并发控制、连接池优化。
-   **高安全性**: Redis SSL 加密、文件深度检测、路径遍历防护。
-   **前端现代化**: 基于 Next.js 框架，提供快速、响应式的用户体验。
-   **全面测试**: 前后端均包含测试，确保代码质量和稳定性。

## 🏗️ 核心架构设计 (Backend Architecture Blueprint)

系统严格遵循 **分层架构 (Layered Architecture)** 原则，通过 **依赖注入 (DI)** 实现模块解耦。

1.  **接入层 (API Layer)** - `api/` 模块化路由:
    -   接口拆分为 chat, files, admin, system，职责单一。
    -   统一网关: 集成 Rate Limiting (限流)、Bandwidth Control (带宽控制) 和 Global Error Handling (全局异常处理)。
    -   安全鉴权: 基于 Bearer Token 的 verify_token 机制，配合 Pydantic 强校验。

2.  **业务逻辑层 (Service Layer)** - `services/`
    -   **ChatService**: 封装 LangGraph 状态机，管理 LLM 调用与流式响应。
    -   **FileService**: 实现 流式上传 (Streaming Upload)，支持 Magic Number 校验、PDF 恶意代码扫描、EPUB 解析，杜绝 OOM (内存溢出) 风险。
    -   **SyncService**: 实现 受控并发 (Semaphore) 的 Notion 增量同步，防止 API 限流。
    -   **AudioService**: 统一封装 TTS 逻辑，支持长文本智能切分与 Markdown 清洗。
    -   **ArchiveService**: 负责会话的异步归档与持久化。

3.  **核心容器层 (Core Layer)** - `core/`
    -   **DI Container**: 纯 Python 实现的轻量级 IoC 容器，统一管理 Config, Redis, VectorStore 等单例的生命周期。
    -   **Lifespan Management**: 统一管理应用启动时的连接预热与关闭时的资源释放。

4.  **基础设施层 (Infrastructure & Data)**
    -   **🔥 Hot (Redis)**: [Session/Cache]
        -   特性: 支持 SSL 加密、连接池复用。
        -   容灾: 实现了 Fallback 降级策略，Redis 宕机时系统自动降级运行，不影响核心服务。
    -   **🧊 Cold (Qdrant + Notion)**: [Long-term Memory]
        -   **Qdrant**: 存储语义向量 (BGE-M3)，支持 Lazy Loading (懒加载) 和 Singleton (单例) 模式。
        -   **Notion**: 知识的最终归档地，保持双写一致性。

## 🛡️ 安全与性能特性 (Security & Performance)

| 维度           | 特性说明                                                                                                                                                                                                                                                                                                                                                        |
|:---------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **安全**       | **Redis SSL**: 强制加密传输，防止内网嗅探。<br> **File Hardening**: 深度检测 PDF 中的恶意 JavaScript，防止 XSS/RCE 攻击。<br> **Path Traversal**: 严格清洗文件名，防止 `../../` 路径遍历攻击。                                                                                                                                                                             |
| **性能**       | **Streaming Upload**: GB 级大文件上传仅占用极低内存 (Chunked Processing)。<br> **Concurrency Control**: 使用 `asyncio.gather` + `Semaphore` 并发同步，效率提升 5x+。<br> **Connection Pooling**: Redis 与 Qdrant 连接池化，避免频繁握手开销。                                                                                                                                               |
| **可观测性**   | **Prometheus Metrics**: 暴露 `/metrics` 接口，监控 QPS、延迟和错误率。                                                                                                                                                                                                                                                                                             |

## 🛠️ 技术栈 (Technologies Used)

### 后端 (Backend)

-   **框架**: FastAPI, Uvicorn
-   **依赖注入**: Pydantic, Pydantic-settings, ItsDangerous
-   **数据库/缓存**: Redis (with hiredis), Qdrant (Vector Store), Notion (Knowledge Base)
-   **AI/LLM**: Langchain, Langchain-community, Langchain-openai, Langgraph, OpenAI
-   **向量嵌入**: FastEmbed (Sparse Vectors 支持)
-   **安全性**: Cryptography, Python-magic, SlowAPI
-   **文件处理**: PyPDF, PDFPlumber, BeautifulSoup4, EbookLib
-   **语音合成**: Edge-TTS, Pydub
-   **其他**: Python-multipart, Python-dotenv, Watchdog, Prometheus-client

### 前端 (Frontend)

-   **框架**: Next.js 15.1, React 19, React-DOM
-   **UI库/工具**: Tailwind CSS 3.4, clsx, lucide-react, tailwind-merge
-   **Markdown处理**: react-markdown, rehype-sanitize, remark-gfm
-   **代码高亮**: highlight.js, rehype-highlight
-   **数学公式**: KaTeX, rehype-katex, remark-math
-   **链接处理**: rehype-external-links
-   **测试**: Vitest, @testing-library/jest-dom, @testing-library/react
-   **开发工具**: TypeScript, ESLint, PostCSS, Autoprefixer

## 📂 目录结构 (Project Structure)

```plaintext
.
├── api/                    # 🚪 后端接口层 (Routes & Dependencies)
│   ├── routes/             #      - chat, files, admin, system 模块化路由
│   └── dependencies.py     #      - FastAPI 依赖注入辅助函数
├── core/                   # 🧠 后端核心层 (IoC Container)
│   ├── container.py        #      - 全局依赖注入容器与生命周期管理
│   └── config.py           #      - 应用配置管理
├── services/               # ⚙️ 后端业务层 (Business Logic)
│   ├── chat_service.py     #      - 对话编排与 LLM 调用
│   ├── file_parser.py      #      - 流式文件解析与安全校验
│   ├── sync_service.py     #      - Notion 增量同步服务
│   ├── audio_service.py    #      - TTS 语音合成服务
│   └── archive_service.py  #      - 会话归档服务
├── agent/                  # 🤖 LangGraph Agent 逻辑
│   └── graph/              #      - 状态机工作流定义
├── notion/                 # 📝 Notion 集成模块
│   └── client.py           #      - Notion API 客户端封装
├── vector/                 # 🔍 向量存储与检索
│   ├── store.py            #      - Qdrant 向量存储管理
│   └── embedding.py        #      - 嵌入模型封装 (Dense + Sparse)
├── tools/                  # 🛠️ Agent 工具集
│   └── search.py           #      - 知识检索工具
├── utils/                  # 🧰 通用工具函数
├── middleware/             # 🔧 FastAPI 中间件
│   ├── auth.py             #      - 认证中间件
│   └── rate_limit.py       #      - 限流中间件
├── infrastructure/         # 🏗️ 后端基础层 (数据库客户端, 缓存等)
│   └── cache/              #      - Redis 客户端与缓存逻辑
├── config/                 # ⚙️ 配置文件
├── tests/                  # 🧪 测试套件
├── web/                    # 🌐 前端 Next.js 应用
│   ├── app/                #      - Next.js App Router 页面
│   ├── components/         #      - React 组件
│   ├── lib/                #      - 前端工具函数与 API 客户端
│   ├── public/             #      - 静态资源
│   ├── styles/             #      - 全局样式
│   ├── package.json        #      - 前端依赖与脚本
│   └── tsconfig.json       #      - 前端 TypeScript 配置
├── venv/                   # 🐍 Python 虚拟环境
├── generated_audio/        # 🔊 TTS 生成的音频文件
├── qdrant_storage/         # 💾 Qdrant 本地数据存储
├── .env                    # 🔒 环境变量 (不提交到 Git)
├── .env.example            # 📝 环境变量示例
├── requirements.txt        # 📝 Python 依赖
├── server.py               # 🚀 后端主应用入口
├── Dockerfile              # 🐳 后端 Dockerfile
├── Dockerfile.frontend     # 🐳 前端 Dockerfile
├── docker-compose.yml      # ⚙️ Docker Compose 配置
├── start.sh                # 🚀 启动脚本
├── deploy.sh               # 🚀 部署脚本
├── CLAUDE.md               # 📝 AI 开发规范
└── README.md               # 📖 项目说明
```

## 🚀 快速开始 (Getting Started)

### 先决条件 (Prerequisites)

-   Python 3.10+
-   Node.js 18+ (包含 npm)
-   Docker (可选，用于容器化部署)
-   Redis 实例 (本地或远程)
-   Qdrant 实例 (本地或远程)
-   Notion API Token (用于 Notion 同步功能)
-   OpenAI API Key (或其他 LLM 服务凭证)

### 1. 克隆仓库 (Clone the Repository)

```bash
git clone https://github.com/your-username/notion-prism-react.git
cd notion-prism-react
```

### 2. 后端设置 (Backend Setup)

#### 创建 Python 虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

#### 配置环境变量

创建 `.env` 文件 (基于 `.env.example`，如果存在的话) 并填写必要的配置，例如：

```dotenv
# .env
OPENAI_API_KEY="your_openai_api_key"
NOTION_API_KEY="your_notion_api_key"
REDIS_URL="redis://localhost:6379"
QDRANT_URL="http://localhost:6333"
# ... 其他后端配置
```

### 3. 前端设置 (Frontend Setup)

进入 `web` 目录并安装 Node.js 依赖:

```bash
cd web
npm install
# 或者使用 yarn / pnpm / bun
```

#### 配置环境变量

前端也可能需要 `.env` 文件，例如 `web/.env.local`：

```dotenv
# web/.env.local
NEXT_PUBLIC_API_URL="http://localhost:8000" # 指向后端API地址
# ... 其他前端配置
```

### 4. 运行应用 (Running the Application)

从项目根目录运行以下命令，同时启动后端和前端:

```bash
npm run dev
```

-   后端 API 将在 `http://localhost:8000` 运行 (默认)。
-   前端应用将在 `http://localhost:3000` 运行 (默认)。

你可以在浏览器中打开 `http://localhost:3000` 访问应用。

### 运行单独服务

如果你只想运行后端或前端:

-   **运行后端**:
    ```bash
    source venv/bin/activate
    uvicorn api.main:app --reload
    # 或者
    # python server.py
    ```
-   **运行前端**:
    ```bash
    cd web
    npm run dev
    ```

### 运行测试 (Running Tests)

-   **后端测试**:
    ```bash
    source venv/bin/activate
    pytest
    ```
-   **前端测试**:
    ```bash
    cd web
    npm run test
    # 或者
    # npm run test:watch
    # npm run test:coverage
    # npm run test:ui
    ```

## ☁️ 部署 (Deployment)

你可以使用 Docker Compose 进行容器化部署，或者参考 `deploy.sh` 脚本进行生产环境部署。

-   **使用 Docker 部署 (开发环境)**:
    ```bash
    docker-compose up --build
    ```

## 📝 开发规范 (Development Guidelines)

本项目遵循严格的开发规范，确保代码质量和可维护性。

### 命名与编码惯例

**Python (后端)**:
- 变量与函数使用 `snake_case`
- 类名使用 `PascalCase`
- 必须使用 Type Hints (类型提示)

**TypeScript (前端)**:
- 组件文件使用 `PascalCase.tsx`
- 普通函数与变量使用 `camelCase`
- 严禁使用 `any` 类型，必须定义具体的 `interface` 或 `type`

### 核心原则

1. **防御性编程**: 所有的 API 调用、数据库查询、文件读取必须包裹在 `try...except` 或 `try...catch` 中
2. **逻辑简洁性**: 优先选择简单的逻辑实现，单个函数尽量控制在 50 行以内
3. **中文文档化**: 复杂逻辑必须在代码上方添加中文注释，解释"为什么要这么做"
4. **不破坏原则**: 禁止删除现有的功能性注释，禁止修改 `.env.example` 之外的 `.env` 本地配置文件

### 验证与测试

- 每次完成修改后，运行 `pytest` 或 `npm run test` 检查是否有语法错误
- 修改 LangGraph 节点逻辑时，必须验证状态机的流转是否闭环

## 🧠 Memory Optimization (内存优化)

BioBrain includes intelligent memory management for large AI models. The system can automatically load/unload models based on usage patterns and memory constraints.

### Configuration Options

Add these environment variables to your `.env` file:

- `ENABLE_SPARSE_MODEL=true` - Enable/disable sparse embedding model (Splade)
- `ENABLE_RERANKER=true` - Enable/disable cross-encoder reranker model
- `MAX_MEMORY_MB=2048` - Maximum memory limit (MB) for model loading decisions
- `SPARSE_MODEL_NAME=prithivida/Splade_PP_en_v1` - Sparse model name
- `RERANKER_MODEL_NAME=BAAI/bge-reranker-large` - Reranker model name

### Production Recommendations

1. **Memory-constrained environments**: Set `ENABLE_SPARSE_MODEL=false` and `ENABLE_RERANKER=false` to disable optional models (~1GB memory saving).
2. **Balanced deployment**: Keep sparse model enabled, disable reranker if memory < 4GB.
3. **High-memory servers**: Increase `MAX_MEMORY_MB` to 4096 or higher for better performance.

### Monitoring

Access the memory monitoring endpoint at `/api/memory` to view current memory usage and model status. Use `/api/memory/cleanup` (POST) to manually trigger cleanup of idle models.

The system automatically unloads models idle for >5 minutes via a background scheduler.

## 🔄 最近更新 (Recent Updates)

### v4.0 重构 (2025-01)
- ✨ 全新整洁架构设计，采用依赖注入模式
- 🚀 升级 LangChain 到 v1.x，LangGraph 到 v1.x
- 🔍 新增 Sparse Vectors 支持 (FastEmbed)
- 📐 前端新增 KaTeX 数学公式渲染
- 💻 前端新增代码高亮 (highlight.js)
- 🔗 新增外部链接安全处理
- 🧪 前后端测试框架完善

## 🤝 贡献 (Contributing)

欢迎提交 Bug 报告、功能请求或 Pull Request。
---
