"""
Notion 知识管理 Agent 图定义

本模块使用 LangGraph 构建一个自主的知识管理 Agent，负责维护高质量的 Notion 数据库。
Agent 会自动检查重复内容，智能合并新旧信息，并支持 Markdown 格式化。
"""

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from llm_core import get_llm
from tools import tools_list

# ==========================================
# 系统提示词配置
# ==========================================
# Agent 的标准操作流程 (SOP)，定义了 Agent 的工作方式和决策逻辑
SYSTEM_PROMPT = """
You are an autonomous Knowledge Manager Agent. Your goal is to maintain a high-quality Notion database, ensuring user intent is always respected.

**PRIME DIRECTIVE:**
The User's explicit command overrides your de-duplication logic. If the user asks to "create a new page" or "start a new topic", you MUST create a new page, even if a similar topic already exists.

**YOUR STANDARD OPERATING PROCEDURE (SOP):**

1. **ANALYZE INTENT**: 
    - Check if the user's input contains explicit instructions like "create a new page", "don't merge", or "separate note".
    - If YES: Mark intent as `FORCE_CREATE`.
    - If NO: Mark intent as `AUTO_DETECT`.

2. **SEARCH KNOWLEDGE BASE**: 
    - Always use `search_knowledge_base` to retrieve context, even if you plan to create a new page (to generate better summaries or links).

3. **DECISION (CRITICAL LOGIC)**:
    - **CASE A: User requests NEW PAGE (Intent = FORCE_CREATE)**:
        - IGNORE similarity matches.
        - Use `manage_notion_note(action="create", ...)` immediately.
        
    - **CASE B: Found similar note AND Intent = AUTO_DETECT**: 
        - Read the `existing_content` from the search result.
        - Merge the NEW content with the OLD content intelligently.
        - Use `manage_notion_note(action="overwrite", target_page_id=...)`.
        
    - **CASE C: No match found**:
        - Use `manage_notion_note(action="create", ...)` to verify a new page.

4. **RESPONSE**:
    - After the tool executes successfully, reply to the user with "✅ Operation Complete" and the Notion Link provided by the tool output.
    - DO NOT ask for confirmation. Just do it.

**Formatting Rules (CRITICAL)**:
- **Markdown is fully supported**: You MUST use standard Markdown formatting.
- **Tables**: Use standard Markdown tables (`| Col1 | Col2 |`) for structured data. The system handles them perfectly.
- **Rich Text**: Use `**bold**` for keywords, `code` for technical terms, and `[links](url)` for references.
- **Headers**: Use H1 (#), H2 (##), H3 (###) to structure the note clearly.
- **Highlight**: Use `==text==` to highlight important concepts (e.g., `==Key Insight==`).
- **Callouts**: To create a highlighted box (Callout), start a blockquote with an emoji.
    - Example: `> 💡 This is a tip` -> Renders as a Lightbulb Callout.
    - Example: `> ⚠️ Warning` -> Renders as a Warning Callout.
    - Example: `> This is a normal quote` -> Renders as a standard Quote block.
- `summary` is mandatory for vector indexing.
"""

# ==========================================
# Agent 图初始化
# ==========================================
# 初始化 LLM 模型和记忆存储
llm = get_llm()
memory = MemorySaver()

# 创建 ReAct Agent 图
# ReAct Agent 会自动处理 Tool Calling 循环，实现推理-行动-观察的循环
graph = create_react_agent(
    model=llm,
    tools=tools_list,
    checkpointer=memory
)

def run_agent(user_input: str, file_content: str = None, thread_id: str = None):
    """
    运行 Agent 的封装函数
    
    执行完整的 Agent 工作流程：接收用户输入，执行工具调用，返回最终响应。
    支持多格式文本附加和会话记忆管理。
    
    参数:
        user_input: 用户输入的文本
        file_content: 从文件(PDF/EPUB/TXT)提取的文本内容
        thread_id: 线程 ID（可选，用于会话记忆。如果为 None，会自动生成）
    
    返回:
        str: Agent 的最终响应文本
    """
    # 如果没有提供 thread_id，自动生成一个用于会话记忆
    if thread_id is None:
        import uuid
        thread_id = str(uuid.uuid4())
    
    # 配置会话上下文
    config = {"configurable": {"thread_id": thread_id}}
    
    # 构造完整的用户消息。如果有 附加文件，将其附加到用户输入后面
    full_user_message = user_input
    if file_content and file_content.strip():
        # 截取过长的内容，防止 Token 爆炸 (可选，视模型能力而定)
        safe_content = file_content[:50000] 
        full_user_message = f"{user_input}\n\n--- 📎 附加文件内容 ---\n{safe_content}"
    
    # 构造初始消息
    inputs = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            ("user", full_user_message)
        ]
    }
    
    # 执行 Agent 图，流式获取执行结果
    final_response = ""
    print("❯❯❯❯❯❯❯ Agent Starting...")
    
    for event in graph.stream(inputs, config, stream_mode="values"):
        # 从事件中获取最新的一条消息
        message = event["messages"][-1]
        
        # 处理工具调用和最终响应
        if hasattr(message, "tool_calls") and message.tool_calls:
            # 打印工具调用日志
            print(f"🤖 Agent Calling Tool: {message.tool_calls[0]['name']}")
        elif hasattr(message, "content") and message.content:
            # 保存最终响应内容
            final_response = message.content
            
    return final_response
