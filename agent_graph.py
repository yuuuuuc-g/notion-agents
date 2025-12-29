from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from llm_core import get_llm
from tools import tools_list

# 1. 系统提示词 (Agent 的 SOP)
SYSTEM_PROMPT = """
You are an autonomous Knowledge Manager Agent. Your goal is to maintain a high-quality, non-duplicate Notion database.

**YOUR STANDARD OPERATING PROCEDURE (SOP):**

1. **RECEIVE INPUT**: User sends a note or content.
2. **SEARCH FIRST (CRITICAL)**: Use `search_knowledge_base` to check if this topic exists.
3. **DECISION**:
    - **CASE A: Found similar note**: 
        - Read the `existing_content` from the search result.
        - Merge the NEW content with the OLD content intelligently.
        - Use `manage_notion_note(action="overwrite", target_page_id=...)`.
    - **CASE B: No match found**:
        - Use `manage_notion_note(action="create", ...)` to verify a new page.
4. **RESPONSE**:
    - After the tool executes successfully, reply to the user with "✅ Operation Complete" and the Notion Link provided by the tool output.
    - DO NOT ask for confirmation. Just do it.

**Formatting Rules (CRITICAL)**:
- **Markdown is fully supported**: You MUST use standard Markdown formatting.
- **Tables**: Use standard Markdown tables (`| Col1 | Col2 |`) for structured data. The system handles them perfectly.
- **Rich Text**: Use `**bold**` for keywords, `code` for technical terms, and `[links](url)` for references.
- **Headers**: Use H1 (#), H2 (##), H3 (###) to structure the note clearly.
- `summary` is mandatory for vector indexing.
"""
# 2. 初始化组件
llm = get_llm()
memory = MemorySaver()

# 3. 创建 ReAct Agent (自动处理 Tool Calling 循环)
# 这行代码替代了以前几十行的 add_node / add_edge
graph = create_react_agent(
    model=llm,
    tools=tools_list,
    checkpointer=memory
)

def run_agent(user_input: str, pdf_text: str = None, thread_id: str = None):
    """
    运行 Agent 的封装函数
    
    参数:
        user_input: 用户输入的文本
        pdf_text: 从 PDF 提取的文本（可选）
        thread_id: 线程 ID（可选，用于会话记忆）
    """
    if thread_id is None:
        import uuid
        thread_id = str(uuid.uuid4())
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 构造用户消息：如果有 PDF 文本，将其附加到用户输入
    full_user_message = user_input
    if pdf_text and pdf_text.strip():
        full_user_message = f"{user_input}\n\n--- PDF 内容 ---\n{pdf_text}"
    
    # 构造初始消息
    inputs = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            ("user", full_user_message)
        ]
    }
    
    # 执行图
    final_response = ""
    print("🚀 Agent Starting...")
    
    for event in graph.stream(inputs, config, stream_mode="values"):
        # 获取最新的一条消息
        message = event["messages"][-1]
        
        # 打印日志 (可选)
        if hasattr(message, "tool_calls") and message.tool_calls:
            print(f"🤖 Agent Calling Tool: {message.tool_calls[0]['name']}")
        elif hasattr(message, "content") and message.content:
            final_response = message.content
            
    return final_response


# ==========================================
# 🔌 本地运行入口 (CLI Mode)
# ==========================================
if __name__ == "__main__":
    import uuid
    import sys
    
    # 1. 生成一个固定的会话 ID，这样在这一轮运行中 Agent 有记忆
    thread_id = str(uuid.uuid4())
    
    print("\n" + "="*50)
    print(f"🤖 Notion Agent Terminal Mode")
    print(f"🧵 Thread ID: {thread_id}")
    print("💡 Tips: 输入 'exit', 'quit' 或按 Ctrl+C 退出")
    print("="*50 + "\n")

    while True:
        try:
            # 2. 获取用户输入
            user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                print("👋 Bye!")
                break
            
            # 3. 调用 Agent (本地测试通常没有 PDF，传 None)
            # run_agent 内部已经包含了打印日志的逻辑
            response = run_agent(
                user_input=user_input, 
                pdf_text=None, 
                thread_id=thread_id
            )
            
            # 4. 打印最终回复 (run_agent 已经打印了过程，这里打印最终结果)
            print(f"\n🤖 Agent:\n{response}\n")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n\n👋 User Interrupted. Bye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")