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




🌟 Exocortex (Notion-Prism-React) 项目全面审计报告
📊 执行摘要
经过对 Exocortex 项目的深入分析，本报告从架构耦合度、技术栈现代性和重构路线图三个维度进行全面评估。项目整体架构设计良好，遵循分层原则，技术选型均为稳定版本。主要问题集中在模块耦合度偏高、全局配置扩散、以及表示层职责过重。
总体评分：B+ (良好但有优化空间)
---
1. 🏗️ 核心模块耦合度分析
1.1 当前架构现状
项目采用经典的分层架构，但存在跨层直接依赖问题：
| 层 | 文件示例 | 依赖问题 |
|----|----------|----------|
| 表示层 | server.py | 直接导入领域层模块 (agent, notion, vector) |
| 应用层 | agent_graph.py | 直接依赖基础设施层 (llm, tools) |
| 领域层 | notion_ops.py | 直接依赖配置全局状态 |
| 基础设施层 | vector_store.py | 与领域逻辑混合 |
1.2 主要耦合问题
1.2.1 违反依赖倒置原则 (DIP)
- 问题：高层模块 server.py 直接依赖低层模块 (vector.vector_store, agent.agent_graph)
- 影响：变更传播风险高，难以进行单元测试
- 证据：
    # server.py 中的直接依赖
  from vector.vector_store import add_memory, search_memory
  from agent.agent_graph import graph
  from notion.block_builder import markdown_to_blocks

1.2.2 配置全局状态耦合
- 问题：config/settings.py 被多个模块直接导入，形成全局可变状态
- 影响：测试困难，隐藏依赖关系，违反单一职责原则
- 证据：7个不同模块直接导入 SETTINGS
1.2.3 基础设施与领域逻辑混合
- 问题：vector_store.py 同时处理 ChromaDB 操作和业务逻辑（父子索引策略）
- 影响：难以替换向量数据库实现，技术债务积累
1.2.4 前端与后端 API 契约紧耦合
- 问题：前端组件直接依赖后端 API 响应格式（如 AUDIO_URL: ... 正则匹配）
- 影响：API 变更需同步修改前端，部署耦合度高
1.3 耦合度评分：中等偏高 (6.5/10)
- 正面：目录结构清晰，模块职责相对明确
- 负面：跨层依赖严重，缺乏接口抽象，全局配置扩散
---
2. 🚀 技术栈现代性评估
2.1 当前技术栈概览
| 类别 | 技术选型 | 版本 | 状态评估 |
|------|----------|------|----------|
| 后端框架 | FastAPI | 0.115.6 | ✅ 稳定版 |
| 代理编排 | LangGraph | 0.2.0+ | ✅ 新兴但专为 Agent 设计 |
| 向量数据库 | ChromaDB | 0.5.0+ | ✅ 轻量但生产扩展性有限 |
| 嵌入模型 | SiliconFlow (BGE-M3) | - | ✅ 中文 SOTA 模型 |
| 缓存 | Redis | 5.0.0+ | ✅ 行业标准 |
| 元数据存储 | SQLite | 最新 | ⚠️ 适合开发，生产需升级 |
| 前端框架 | Next.js | 15.1.0 | ✅ 稳定版 |
| UI 库 | React | 19.0.0 | ✅ 最新稳定版 |
| 样式框架 | Tailwind CSS | 3.4.16 | ✅ 稳定版 |
| 部署 | Docker Compose | 最新 | ✅ 标准容器编排 |
2.2 推荐替代方案对比
2.2.1 向量数据库生产化选择
| 选项 | 适用场景 | 性能特点 | 推荐度 |
|------|----------|----------|--------|
| ChromaDB | 开发/小规模生产 | 轻量，简单 | ⭐⭐⭐ |
| Qdrant | 中大规模生产 | 高性能，Rust 编写 | ⭐⭐⭐⭐⭐ |
| Weaviate | 企业级功能需求 | 内置 ML 模块，GraphQL | ⭐⭐⭐⭐ |
| Pinecone | 完全托管需求 | 免运维，成本较高 | ⭐⭐⭐ |
建议：评估 Qdrant 作为生产替代，平衡性能与复杂度。
2.2.2 数据库升级建议
- 短期：SQLite + 连接池优化
- 中期：迁移到 PostgreSQL，支持并发和复杂查询
- 长期：考虑 TimescaleDB（时序数据）扩展
2.2.3 前端技术栈优化
- 状态管理：考虑引入 Zustand 或 Redux Toolkit 替代 useState 扩散
- 组件库：建立通用 UI 组件库提升复用性
- API 封装：创建 services 层统一 API 调用
---
3. 🗺️ 详细重构路线图
📅 阶段 1：架构解耦 (1-2周)
| 任务 | 具体措施 | 预期收益 |
|------|----------|----------|
| 1.1 依赖注入容器 | 引入 dependency-injector 或 injector 库 | 解耦模块创建逻辑 |
| 1.2 接口抽象 | 定义领域接口 (IVectorStore, INotionClient, IAgentOrchestrator) | 支持实现替换 |
| 1.3 配置重构 | 将 SETTINGS 改为依赖注入，移除全局导入 | 提升可测试性 |
| 1.4 服务层引入 | 创建 Service 层协调领域对象 | 分离业务流程与技术实现 |
重构后示例：
# 依赖注入示例
class VectorService:
    def __init__(self, vector_store: IVectorStore, config: Config):
        self.store = vector_store
        self.config = config

    def add_memory(self, text: str) -> str:
        # 业务逻辑 + 技术调用分离
        pass
📅 阶段 2：基础设施分离 (2-3周)
| 任务 | 具体措施 | 预期收益 |
|------|----------|----------|
| 2.1 仓储模式 | 实现 Repository 模式包装数据访问 | 数据库实现可替换 |
| 2.2 适配器层 | 创建 adapters/ 目录存放外部服务集成 | 第三方服务变更隔离 |
| 2.3 事件驱动 | 引入领域事件，解耦模块间同步调用 | 系统可扩展性提升 |
| 2.4 缓存抽象 | 统一缓存接口，支持多级缓存策略 | 性能优化空间 |
📅 阶段 3：前端重构 (1-2周)
| 任务 | 具体措施 | 风险控制 |
|------|----------|----------|
| 3.1 组件拆分 | page.tsx 拆分为多个子组件 | 逐步迁移，兼容性测试 |
| 3.2 API 封装 | 创建 services/api.ts 统一调用 | 保持向后兼容 |
| 3.3 状态管理 | 引入 Zustand 或 Jotai | 小范围试点 |
| 3.4 类型安全 | 完善 TypeScript 类型定义 | 逐步增强 |
📅 阶段 4：质量与测试 (持续)
| 任务 | 具体措施 | 验收标准 |
|------|----------|----------|
| 4.1 测试金字塔 | 单元测试(70%) + 集成测试(20%) + E2E(10%) | 覆盖率 > 80% |
| 4.2 CI/CD 流水线 | GitHub Actions 自动化测试、构建、部署 | 部署时间 < 10min |
| 4.3 监控告警 | 关键指标监控（响应时间、错误率、向量召回率） | SLA 99.5% |
| 4.4 文档自动化 | OpenAPI 自动生成，架构决策记录(ADR) | 文档覆盖率 100% |
📅 阶段 5：性能与扩展 (长期)
| 任务 | 具体措施 | 性能目标 |
|------|----------|----------|
| 5.1 向量索引优化 | HNSW 索引调优，批量插入优化 | 查询延迟 < 100ms |
| 5.2 异步任务队列 | Celery + Redis 处理耗时操作（Notion 同步） | 任务吞吐 > 1000/min |
| 5.3 数据库分片 | 按领域/时间分片向量和元数据存储 | 存储容量 > 10TB |
| 5.4 CDN 缓存 | 静态资源、音频文件 CDN 加速 | 全球访问延迟 < 200ms |
---
4. 📋 优先级矩阵
| 优先级 | 任务 | 影响度 | 实施难度 | 时间估算 |
|--------|------|--------|----------|----------|
| P0 | 配置管理依赖注入改造 | 高 | 中 | 5天 |
| P0 | server.py 职责精简 | 高 | 中 | 3天 |
| P1 | 向量存储接口抽象 | 中 | 中 | 3天 |
| P1 | 前端 API 服务层封装 | 中 | 低 | 2天 |
| P2 | PostgreSQL 迁移评估 | 高 | 高 | 14天 |
| P2 | 单元测试框架建立 | 中 | 中 | 10天 |
| P3 | 事件驱动架构改造 | 低 | 高 | 21天 |
---
5. ✅ 审计结论与建议
5.1 架构健康度：B+ (良好但有优化空间)
优势：
- ✅ 分层清晰，模块划分合理
- ✅ 技术选型前瞻，版本管理良好
- ✅ 已开始引入接口抽象和依赖注入
风险：
- ⚠️ 耦合度偏高，测试覆盖不足
- ⚠️ 全局配置扩散，违反单一职责原则
- ⚠️ 表示层职责过重
5.2 立即行动项 (本周)
1. 版本稳定化：确认所有依赖均为稳定版本
2. 依赖隔离：开始接口抽象，至少为 VectorStore 和 NotionClient 定义完整接口
3. 测试起步：为核心业务逻辑添加单元测试（agent_graph、vector_store）
5.3 中长期战略 (1-3月)
1. 生产就绪向量库：评估并迁移到 Qdrant 或 Weaviate
2. 数据库升级：SQLite → PostgreSQL 迁移规划
3. 监控体系：建立完整的可观测性栈
5.4 技术债务管理建议
- 每周：分配 20% 开发时间处理技术债务
- 每月：架构评审会议，评估耦合度指标
- 每季度：技术栈评估，跟进生态系统变化
---
🎯 最终建议
Exocortex 项目基础架构扎实，具备良好的演进潜力。建议按阶段实施重构路线图，优先解决版本稳定性和核心模块解耦问题。短期内保持技术栈稳定，中长期逐步引入更生产就绪的组件。
关键成功因素：
1. 保持向后兼容的渐进式重构
2. 每个阶段都有可验证的交付物
3. 建立自动化测试保障重构安全
4. 团队共识和持续的技术债务管理
通过本路线图的实施，项目可望在 3-6 个月 内达到生产级架构成熟度，支持大规模用户和复杂业务场景。
---
📈 监控指标建议
| 指标类别 | 具体指标 | 目标值 |
|----------|----------|--------|
| 代码质量 | 耦合度评分 | < 5.0/10 |
| 代码质量 | 测试覆盖率 | > 80% |
| 代码质量 | 循环复杂度 | < 10 |
| 性能指标 | API 响应时间 | < 200ms |
| 性能指标 | 向量查询延迟 | < 100ms |
| 性能指标 | 内存使用率 | < 70% |
| 业务指标 | 向量召回率 | > 85% |
| 业务指标 | 用户满意度 | > 4.5/5 |
建议工具：
- pylint/pylint：代码质量检查
- mypy：类型检查
- pytest：测试框架
- pre-commit hooks：代码规范
- Prometheus + Grafana：监控告警
