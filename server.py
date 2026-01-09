"""
server.py
Backend API 入口 (FastAPI)
负责接收 HTTP 请求，并调用 Agent Graph 进行处理
"""
import os
import re
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional


from agent.agent_graph import graph
from langchain_core.messages import HumanMessage

from config.settings import SETTINGS

# --- 初始化 APP ---
app = FastAPI(
    title="Exocortex API", 
    description="Backend service for Notion-Prism-React Agent",
    version="2.0.0" # 架构升级，版本号 +1
)

# --- 1. 配置 CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. 挂载静态文件目录 ---
# 使用全局统一配置，防止路径不一致
AUDIO_DIR = SETTINGS.AUDIO_DIR

# 确保目录存在 (虽然 audio_ops 也会创建，但 Server 启动时最好检查一下)
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# --- 3. 定义数据模型 ---
class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default_user"
    model_name: Optional[str] = "deepseek/deepseek-chat"

class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    notion_url: Optional[str] = None
    thread_id: str

# --- 4. 辅助函数 ---
def extract_and_convert_paths(text: str, base_url: str) -> tuple[str, str | None]:
    """
    提取生成的音频文件路径，并转换为可访问的 URL
    """
    audio_url = None
    clean_text = text
    # 正则匹配 audio_ops 生成的文件名格式
    match = re.search(r"generated_audio[\\/](audio_[a-f0-9]+\.mp3)", text, re.IGNORECASE)
    
    if match:
        filename = match.group(1)
        # 构造 URL: http://localhost:8000/audio/xxx.mp3
        audio_url = f"{base_url}/audio/{filename}"
    
    return clean_text, audio_url

# --- 5. 核心聊天接口 ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, req_context: Request):
    # 打印日志，方便观察请求
    print(f"📨 Query: {request.query} | Thread: {request.thread_id}")
    
    try:
        # 构造 LangGraph 需要的输入
        config = {"configurable": {"thread_id": request.thread_id}}
        inputs = {
            "messages": [
                HumanMessage(content=request.query)
            ]
        }
        
        # 运行 Agent (异步调用)
        # 注意：这里调用的是 agent.agent_graph 里定义好的 graph
        final_state = await graph.ainvoke(inputs, config=config)
        
        # 提取回复
        messages = final_state["messages"]
        last_message = messages[-1]
        raw_response = last_message.content
        
        # 处理文件路径
        base_url = str(req_context.base_url).rstrip("/")
        final_text, audio_url = extract_and_convert_paths(raw_response, base_url)
        
        return ChatResponse(
            text=final_text,
            audio_url=audio_url,
            thread_id=request.thread_id
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

# --- 6. 健康检查 ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Exocortex Brain (v2.0 Refactored)"}

if __name__ == "__main__":
    # 本地启动
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)