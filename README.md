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
-   **依赖注入**: Pydantic, ItsDangerous
-   **数据库/缓存**: Redis (with hiredis), Qdrant (Vector Store), Notion (Knowledge Base)
-   **AI/LLM**: Langchain, Langchain-community, Langchain-openai, Langgraph, OpenAI
-   **安全性**: Cryptography, Python-magic, SlowAPI
-   **文件处理**: PyPDF, PDFPlumber, BeautifulSoup4, EbookLib
-   **其他**: Python-multipart, Python-dotenv, Watchdog, Prometheus-client, Edge-tts, Pydub

### 前端 (Frontend)

-   **框架**: Next.js, React, React-DOM
-   **UI库/工具**: Tailwind CSS, clsx, lucide-react, tailwind-merge
-   **Markdown处理**: react-markdown, rehype-sanitize, remark-gfm
-   **测试**: Vitest, @testing-library/jest-dom, @testing-library/react
-   **开发工具**: Autoprefixer, ESLint, TypeScript

## 📂 目录结构 (Project Structure)

```plaintext
.
├── api/                    # 🚪 后端接口层 (Routes & Dependencies)
│   ├── routes/             #      - chat, files, admin, system 模块化路由
│   └── dependencies.py     #      - FastAPI 依赖注入辅助函数
├── core/                   # 🧠 后端核心层 (IoC Container)
│   └── container.py        #      - 全局依赖注入容器与生命周期管理
├── services/               # ⚙️ 后端业务层 (Business Logic)
│   ├── chat_service.py     #      - 对话编排与 LLM 调用
│   ├── file_parser.py      #      - 流式文件解析与安全校验
│   ├── sync_service.py     #      - Notion 增量同步服务
│   ├── audio_service.py    #      - TTS 语音合成服务
│   └── archive_service.py  #      - 会话归档服务
├── infrastructure/         # 🏗️ 后端基础层 (数据库客户端, 缓存等)
│   └── cache/              #      - Redis 客户端与缓存逻辑
├── web/                    # 🌐 前端 Next.js 应用
│   ├── app/                #      - Next.js 页面与组件
│   ├── public/             #      - 静态资源
│   ├── styles/             #      - 全局样式
│   ├── components/         #      - React 组件
│   ├── lib/                #      - 前端工具函数
│   ├── package.json        #      - 前端依赖与脚本
│   └── tsconfig.json       #      - 前端 TypeScript 配置
├── venv/                   # 🐍 Python 虚拟环境
├── node_modules/           # 📦 Node.js 依赖
├── package.json            # 📋 根目录 Node.js 依赖与项目脚本
├── requirements.txt        # 📝 Python 依赖
├── server.py               # 🚀 后端主应用入口
├── Dockerfile              # 🐳 后端 Dockerfile
├── Dockerfile.frontend     # 🐳 前端 Dockerfile
├── docker-compose.yml      # ⚙️ Docker Compose 配置
├── start.sh                # 🚀 启动脚本
└── deploy.sh               # 部署脚本 (例如：CI/CD)
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
    npm run dev:server
    # 或者直接
    # source venv/bin/activate
    # python server.py
    ```
-   **运行前端**:
    ```bash
    npm run dev:web
    # 或者进入 web 目录后
    # cd web
    # npm run dev
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

## 🤝 贡献 (Contributing)

欢迎提交 Bug 报告、功能请求或 Pull Request。

---
