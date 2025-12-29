```markdown
# 💠 Notion-Prism-React

> **一个由 LangGraph 驱动的智能知识管理 Agent。**
> 拒绝信息堆砌，构建一个高质量、非重复、可长期演进的个人知识库。

**Notion-Prism-React** 是一个基于 ReAct 架构的自动化知识管理系统。它能够接收文本或 PDF 输入，通过语义检索自动判断是“新建笔记”还是“融合旧知”，并自动处理 Notion 格式排版与向量索引同步。

---

## ✨ 核心特性

### 🧠 智能决策 (ReAct Agent)
- **LangGraph 驱动**：基于 ReAct (Reason + Act) 模式，Agent 拥有独立的思考与决策能力。
- **自主闭环**：自动执行 `搜索` → `决策` → `执行` (创建/合并) → `同步` 的完整流程。
- **会话记忆**：支持基于 `thread_id` 的多轮对话上下文记忆。

### 🔍 语义去重与融合
- **知识完备性检查**：在写入前，Agent 始终先搜索向量库中的现有笔记。
- **智能合并**：若发现相似主题，自动读取旧内容并与新知融合（Merge），避免知识库产生冗余碎片。

### 🛠️ 强大的工程化实现
- **Notion 深度集成**：
  - 自动将 Markdown 转换为 Notion Blocks。
  - **自动分片写入**：完美解决 Notion API 单次请求 `block ≤ 100` 的限制。
- **PDF 全流程支持**：
  - UI 直接上传 PDF，自动解析为文本并注入 Agent 上下文。
  - 向量索引策略：始终使用完整语义文本进行索引，而非碎片化 Chunk，保证检索精度。
- **双向同步**：每次 Notion 写入成功后，自动同步更新 Vector DB，确保“大脑”与“笔记本”一致。

---

## 🏗️ 系统架构

### 📂 项目结构

```text
notion-prism-react/
├── app.py                # 🖥️ Streamlit UI：负责聊天交互与文件上传
├── agent_graph.py        # 🧠 Brain：LangGraph ReAct Agent 的核心定义
├── tools.py              # 🛠️ Tools：封装给 Agent 调用的工具（搜索库/操作Notion）
├── notion_ops.py         # 🧱 Ops：Notion API 底层封装 (Markdown解析/分批写入)
├── vector_ops.py         # 💾 Ops：向量数据库操作 (Search / Add)
├── llm_core.py           # 🔌 Core：LLM 模型初始化配置
├── requirements.txt      # 📦 依赖清单
└── README.md

```

### 🔄 工作流 (Workflow)

```
graph TD
    User[用户输入 (文本/PDF)] --> Agent
    
    subgraph "ReAct Loop"
        Agent[🤖 Agent] --> Search{🔍 向量搜索}
        Search -- 发现相似笔记 --> Merge[⚗️ 决策: 合并内容]
        Search -- 无重复 --> Create[📝 决策: 新建页面]
    end
    
    Merge & Create --> Write[Notion API (Block切片)]
    Write --> Sync[💾 同步至 Vector DB]
    Sync --> Response[✅ 返回 Notion 链接]

```

---

## 🚀 快速开始

### 1. 安装依赖

确保 Python 环境已就绪（建议 Python 3.10+）：

```bash
pip install -r requirements.txt

```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件，填入以下配置：

```ini
OPENAI_API_KEY=sk-xxxx
# Notion 集成配置
NOTION_TOKEN=secret_xxxx
NOTION_DATABASE_ID=xxxx

```

### 3. 启动应用

```bash
streamlit run app.py

```

浏览器自动打开后即可开始使用。

---

## 📖 使用指南

### 文本交互

直接在对话框输入笔记内容或知识点，Agent 会自动判断并处理。

### PDF 处理流程

1. 在文件栏上传 PDF 文件。
2. 在对话框输入指令，例如：
> "请整理这份文档的核心观点并写入 Notion"


3. **Agent 将执行：**
* 解析 PDF 文本 -> 注入上下文 -> 检索查重 -> 写入 Notion -> 建立索引。



> **💡 Note:** PDF 内容在存入向量库时，会以语义完整的形式索引，而不是机械地按页切割，这有助于提高后续问答的召回率。

---

## 🧠 Agent 行为规范 (SOP)

为了保证知识库的整洁，Agent 被硬编码遵循以下 **标准作业程序 (SOP)**：

1. **Search First**：任何写入请求前，**必须**先调用 `search_knowledge_base`。
2. **Autonomous Decision**：
* 🔴 **Found (命中)**：调用 `overwrite` 模式，进行知识融合。
* 🟢 **Not Found (未命中)**：调用 `create` 模式，新建页面。


3. **Zero-Touch**：不需要向用户请求确认，直接执行决策。
4. **Final Response**：操作完成后，仅返回 `✅ Operation Complete` 及对应的 Notion 链接。

---

## 🛡️ 工程鲁棒性 (Robustness)

本项目已解决以下关键工程问题，适合长期稳定运行：

* ✅ **Notion 写入限制**：自动处理 block 数量超过 100 时的分页追加 (Pagination Append)。
* ✅ **数据一致性**：解决了向量库与 Notion 内容不同步的问题。
* ✅ **PDF 通路**：修复了文件流在 Agent 上下文中丢失或解析为空的问题。
* ✅ **工具稳定性**：严格的 Tool Argument Schema，防止 Agent 调用参数错误。

---

## 🔧 未来规划

* [ ] **多知识域支持**：根据内容自动路由到不同的 Notion Database (e.g., Tech, Reading, Life)。
* [ ] **高级分块**：引入 Chunk-level 的细粒度向量索引。
* [ ] **多 Agent 协作**：引入 Reviewer Agent 对笔记质量进行二次审查。
* [ ] **Web API 部署**：利用 FastAPI 封装为后端服务。

---

## 📜 License

MIT License.
Designed for personal knowledge management and learning purposes.

```

```
