"""
agent/agent_graph.py
Agent 思考结构定义
"""
from typing import List, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig  # 🔥 新增导入
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

# 👇 引入配置，用于判断模式
from config.settings import SETTINGS

# 👇 修改引用：去 llm 包里找
from llm.llm_provider import get_llm

# 👇 修改引用：去 tools 包里找
from tools.tools import tools_list

# 👇 引用提示词
from .prompts import SYSTEM_PROMPT

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
    def simple_chat_node(state: State, config: RunnableConfig):  # 🔥 引入 config
        messages = state["messages"]
        last_msg = messages[-1]
        last_content = (
            last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        )

        # 🔥 核心逻辑：尝试从 config 的 configurable 字典中获取模型
        # 如果 server.py 没传，就用全局定义的默认 llm
        active_llm = config.get("configurable", {}).get("model", llm)

        response = active_llm.invoke(last_content)
        return {"messages": [AIMessage(content=str(response))]}

    # 手动构建一个最简单的图: Start -> Chat -> End
    workflow = StateGraph(State)
    workflow.add_node("agent", simple_chat_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)

    graph = workflow.compile(checkpointer=memory)

else:
    # --- 模式 B: 智能体模式 ---
    # 修改这里：我们不再直接传入固定的 llm，而是保持 graph 的灵活性

    # 先定义一个默认模型作为兜底
    default_llm = get_llm()

    # 注意：create_react_agent 编译后是一个可调用的对象
    # 我们可以在调用它的 astream_events 时，通过参数覆盖模型
    graph = create_react_agent(
        model=default_llm,  # 默认值
        tools=tools_list,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT,
    )
