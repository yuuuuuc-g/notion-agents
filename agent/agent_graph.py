"""
agent/agent_graph.py
Agent 思考结构定义
重构版 v3.0: 适配 DI 容器，移除旧的 llm_provider 依赖
"""

from langgraph.checkpoint.memory import MemorySaver
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

# --- 🔥 智能体模式 (Standard ReAct Agent) ---
# 已移除本地 NanoGPT 模式，仅保留完整的工具调用能力

# create_react_agent 能够自动处理工具调用循环
# 这里的 model 参数会被 ChatService 传入的 configurable['model'] 覆盖
graph = create_react_agent(
    model=default_llm,
    tools=tools_list,
    checkpointer=memory,
    prompt=SYSTEM_PROMPT,  # LangGraph v0.2+ 推荐用 state_modifier 传入 System Prompt
)
