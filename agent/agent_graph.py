"""
agent/agent_graph.py
Agent 思考结构定义
重构版 v3.0: 适配 DI 容器，移除旧的 llm_provider 依赖
"""
from typing import List, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

# 🔥 核心：引入全局容器
from core.container import container

# 引入工具集
from tools.tools import tools_list

# 引入提示词
from .prompts import SYSTEM_PROMPT

# ==========================================
# Agent 图初始化
# ==========================================

# 1. 从容器获取默认配置和模型
# 这里的模型仅作为 Graph 初始化时的“占位符”或默认值
# 实际请求中，ChatService 会通过 configurable 动态传入特定模型
settings = container.config()
default_llm = container.llm_factory()

memory = MemorySaver()

# --- 🟢 分支判断：根据配置模式创建不同的大脑 ---

if settings.USE_LOCAL_NANOGPT:
    # -------------------------------------------
    # 模式 A: 笨小孩模式 (本地 NanoGPT / 调试用)
    # -------------------------------------------
    print("⚠️ [Agent] Running in LOCAL mode (No Tools Support).")

    # 定义简单的状态
    class State(TypedDict):
        messages: List[Union[HumanMessage, AIMessage]]

    # 定义一个最简单的节点：只调用模型，不调用工具
    def simple_chat_node(state: State, config: RunnableConfig):
        messages = state["messages"]
        last_msg = messages[-1]
        last_content = (
            last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        )

        # 🔥 核心逻辑：运行时动态获取模型
        # 优先从 config 获取 (由 ChatService 注入)，否则用默认的
        active_llm = config.get("configurable", {}).get("model", default_llm)

        response = active_llm.invoke(last_content)
        return {"messages": [AIMessage(content=str(response))]}

    # 手动构建图
    workflow = StateGraph(State)
    workflow.add_node("agent", simple_chat_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)

    graph = workflow.compile(checkpointer=memory)

else:
    # -------------------------------------------
    # 模式 B: 智能体模式 (Standard ReAct Agent)
    # -------------------------------------------

    # create_react_agent 能够自动处理工具调用循环
    # 这里的 model 参数会被 ChatService 传入的 configurable['model'] 覆盖
    graph = create_react_agent(
        model=default_llm,
        tools=tools_list,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT,  # LangGraph v0.2+ 推荐用 state_modifier 传入 System Prompt
    )
