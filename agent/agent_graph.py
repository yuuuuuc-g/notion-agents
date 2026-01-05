"""
agent/agent_graph.py
Agent 思考结构定义
"""
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# 👇 修改引用：去 llm 包里找
from llm.llm_provider import get_llm
# 👇 修改引用：去 tools 包里找
from tools.tools import tools_list
# 👇 修改引用：从旁边的 prompts 文件导入
from .prompts import SYSTEM_PROMPT

# ==========================================
# Agent 图初始化
# ==========================================

llm = get_llm()
memory = MemorySaver()

graph = create_react_agent(
    model=llm,
    tools=tools_list,
    checkpointer=memory,
    prompt=SYSTEM_PROMPT # 注意：langgraph 新版参数名可能是 state_modifier 或 prompt，视版本而定
)