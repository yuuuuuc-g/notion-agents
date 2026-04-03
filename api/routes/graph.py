import uuid
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from core.container import container
import logging
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger("biobrain.graph")

class GraphNode(BaseModel):
    id: str
    name: str
    color: str
    val: int
    content: Optional[str] = None

class GraphLink(BaseModel):
    source: str
    target: str

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]

@router.get("/graph", response_model=GraphResponse)
async def get_graph_data(q: Optional[str] = Query(None)):
    """获取知识图谱数据
    - q: 搜索词
    - 返回: 包含中心节点和关联笔记节点的图谱数据
    """
    if not q:
        return {"nodes": [], "links": []}

    try:
        # 获取 Qdrant 向量存储实例
        vector_store = container.vector_store()
        
        # 搜索最相关的6篇笔记
        search_results = await vector_store.search(
            query=q,
            limit=6,
            with_payload=True
        )

        # 构建中心节点
        center_node = GraphNode(
            id="center",
            name=f"检索: {q}",
            color="#ffffff",
            val=20
        )

        nodes = [center_node]
        links = []
        
        # 处理每篇笔记
        for result in search_results:
            if not result.payload:
                continue
                
            payload = result.payload
            note_id = str(result.id)
            title = payload.get("title", "Untitled")
            content = payload.get("content", "")
            
            # 根据分类确定节点颜色
            category = payload.get("category", "").lower()
            if "spanish" in category:
                color = "#ef4444"  # 西语-红色
            elif "tech" in category:
                color = "#3b82f6"  # 科技-蓝色
            elif "humanities" in category:
                color = "#10b981"  # 人文-绿色
            else:
                color = "#aaaaaa"   # 默认-灰色

            # 创建笔记节点
            note_node = GraphNode(
                id=note_id,
                name=title,
                color=color,
                val=10,
                content=content
            )
            nodes.append(note_node)
            
            # 创建与中心节点的连接
            link = GraphLink(
                source="center",
                target=note_id
            )
            links.append(link)

        return {
            "nodes": nodes,
            "links": links
        }

    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"无法获取图谱数据: {str(e)}"
        )
