"""
Notion 知识管理 Agent 图定义

本模块使用 LangGraph 构建一个自主的知识管理 Agent，负责维护高质量的 Notion 数据库。
Agent 会自动检查重复内容，智能合并新旧信息，并支持 Markdown 格式化。
"""
import uuid
import re
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from llm_core import get_llm
from tools import tools_list

# ==========================================
# 系统提示词配置
# ==========================================
# Agent 的标准操作流程 (SOP)，定义了 Agent 的工作方式和决策逻辑
SYSTEM_PROMPT = """
You are an autonomous Multi-modal Knowledge Manager Agent. Your goal is to maintain a high-quality Notion database and provide audio services, ensuring user intent is always respected.

**PRIME DIRECTIVE:**
1. **Audio Efficiency**: If the user asks to generate audio/speech, DO NOT search the knowledge base. Run the audio tool immediately.
2. **User Override**: If the user asks to "create a new page" (for notes), you MUST create a new page, overriding de-duplication logic.

**YOUR STANDARD OPERATING PROCEDURE (SOP):**

1. **CLASSIFY TASK TYPE**:
    - **TYPE: AUDIO**: User wants text-to-speech, audio generation, or "read this".
    - **TYPE: KNOWLEDGE**: User wants to save notes, search info, update Notion, or write articles.

2. **EXECUTE BASED ON TYPE**:

    🟢 **PATH A: IF TYPE = AUDIO** (NO SEARCH REQUIRED):
    - **Step 1**: Identify the target language ('es' for Spanish, 'en' for English). If uncertain/mixed, default to 'es' (Spanish).
    - **Step 2**: Call `convert_text_to_audio(text=..., language=...)` immediately.
    - **Step 3**: STOP. Do not perform vector search unless the user explicitly asks to "find notes AND convert them".

    🔵 **PATH B: IF TYPE = KNOWLEDGE** (SEARCH REQUIRED):
    - **Step 1**: Check for `FORCE_CREATE` intent (explicit instructions to "create new", "don't merge").
    - **Step 2**: **Always** use `search_knowledge_base` to retrieve context.
    - **Step 3**: DECISION LOGIC:
        - **CASE A (Intent = FORCE_CREATE)**: IGNORE matches. Use `manage_notion_note(action="create")`.
        - **CASE B (Found similar + AUTO_DETECT)**: Merge content. Use `manage_notion_note(action="overwrite", target_page_id=...)`.
        - **CASE C (No match)**: Use `manage_notion_note(action="create")`.

3. **RESPONSE**:
    - For Audio: You MUST include the file path in your response. 
      Format: "✅ Audio generated. File path: <insert_path_from_tool_output>"
    - For Notes: Reply with "✅ Operation Complete" and the Notion Link.
    - DO NOT ask for confirmation.

**Formatting Rules (CRITICAL)**:
- **Markdown is fully supported**: Use `**bold**`, `[links](url)`, tables, etc.
- **Callouts**: Use `> 💡` for tips, `> ⚠️` for warnings.
- **Language**: When generating audio, ensure the text sent to the tool is clean text (the tool handles markdown stripping, but you should provide the core content).
"""

# ==========================================
# Agent 图初始化

llm = get_llm()
memory = MemorySaver()

# 创建 ReAct Agent 图
graph = create_react_agent(
    model=llm,
    tools=tools_list,
    checkpointer=memory
)

def run_agent(user_input: str, file_content: str = None, thread_id: str = None):
    """
    运行 Agent 的封装函数
    """
    result = {
        "type": "knowledge",
        "text": "",
        "audio_path": None,
        "notion_url": None
    }
    # 如果没有提供 thread_id，自动生成一个用于会话记忆
    if thread_id is None:
        thread_id = str(uuid.uuid4())
    
    # 配置会话上下文
    config = {"configurable": {"thread_id": thread_id}}
    
    # 构造完整的用户消息。如果有 附加文件，将其附加到用户输入后面
    full_user_message = user_input
    if file_content and file_content.strip():
        safe_content = file_content[:50000] 
        full_user_message = f"{user_input}\n\n--- 📎 附加文件内容 ---\n{safe_content}"
    
    # 构造初始消息
    inputs = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            ("user", full_user_message)
        ]
    }
    
    print("❯❯❯❯❯❯❯ Agent Starting...")
    
    try:
        # ✅ 关键修复：循环逻辑
        for event in graph.stream(inputs, config, stream_mode="values"):
            message = event["messages"][-1]

            # --- A. 捕获 Tool 输出 (必须在循环内部！) ---
            if isinstance(message, ToolMessage):
                
                # 捕获 Audio Tool
                if message.name == "convert_text_to_audio":
                    result["type"] = "audio"
                    # ✅ 关键修复：正则提取纯净路径
                    # Tool 返回: "SUCCESS... File path: /tmp/xyz.mp3 ..."
                    match = re.search(r"File path:\s*(.+?\.mp3)", message.content)
                    if match:
                        result["audio_path"] = match.group(1).strip()
                    else:
                        # 保底逻辑
                        result["audio_path"] = message.content

                # 捕获 Notion Tool
                elif message.name == "manage_notion_note":
                    result["type"] = "knowledge"
                    # 这里预留给未来提取 Notion URL

            # --- B. 捕获 AI 最终回复 ---
            if isinstance(message, AIMessage) and message.content:
                result["text"] = message.content
            
        return result

    except Exception as e:
        print(f"❌ Error during execution: {e}")
        return {"type": "error", "text": f"Agent 运行出错: {str(e)}"}