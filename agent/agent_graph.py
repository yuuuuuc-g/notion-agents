"""
agent/agent_graph.py
Agent 思考结构定义
"""
from typing import TypedDict, List, Union
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage

# 👇 修改引用：去 llm 包里找
from llm.llm_provider import get_llm
# 👇 修改引用：去 tools 包里找
from tools.tools import tools_list
# 👇 引用提示词
from .prompts import SYSTEM_PROMPT
# 👇 引入配置，用于判断模式
from config.settings import SETTINGS

# ==========================================
# Agent 图初始化
# ==========================================

llm = get_llm()
memory = MemorySaver()

# --- 🟢 分支判断：根据模型类型创建不同的大脑 ---

if SETTINGS.USE_LOCAL_NANOGPT:
    # -------------------------------------------
    # 模式 A: 笨小孩模式 (本地 NanoGPT)
    # -------------------------------------------
    print("⚠️ [Agent] Running in LOCAL mode (No Tools Support).")
    
    # 定义简单的状态
    class State(TypedDict):
        messages: List[Union[HumanMessage, AIMessage]]

    # 定义一个最简单的节点：只调用模型，不调用工具
    def simple_chat_node(state: State):
        messages = state["messages"]
        # 直接把对话扔给模型 (注意：NanoGPT 其实也看不懂前面的对话，只会续写最后一句)
        # 但为了跑通流程，我们假装它能看懂
        last_msg = messages[-1]
        last_content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        # 调用我们的 LocalNanoGPT 适配器
        response = llm.invoke(last_content) 
        
        return {"messages": [AIMessage(content=str(response))]}

    # 手动构建一个最简单的图: Start -> Chat -> End
    workflow = StateGraph(State)
    workflow.add_node("agent", simple_chat_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    
    graph = workflow.compile(checkpointer=memory)

else:
    # -------------------------------------------
    # 模式 B: 智能体模式 (DeepSeek/OpenAI)
    # -------------------------------------------
    print("🤖 [Agent] Running in SMART mode (Tools Enabled).")

    graph = create_react_agent(
        model=llm,
        tools=tools_list,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT # 注意：langgraph 新版参数名可能是 state_modifier 或 prompt，视版本而定
    )