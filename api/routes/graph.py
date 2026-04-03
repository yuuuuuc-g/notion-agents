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
        search_results = vector_store.search_with_context(
            query=q,
            top_k=6
        )

        if not search_results["match"]:
            return {"nodes": [], "links": []}

        # 构建中心节点
        center_node = GraphNode(
            id="center",
            name=f"检索: {q}",
            color="#ffffff",
            val=20,
            content=""
        )

        nodes = [center_node]
        links = []
        
        # 处理每篇笔记
        seen_titles = {}  # 用于合并相同标题的笔记内容
        
        for hit in search_results["results"]:
            logger.debug(f"DEBUG PAYLOAD: {hit.payload}")
            
            # 提取标题
            payload = hit.payload or {}
            metadata = payload.get("metadata", {})
            title = (
                metadata.get("title") or 
                metadata.get("source") or 
                payload.get("title") or 
                "Untitled"
            )
            
            # 提取正文内容
            content = payload.get("page_content", "")
            
            # 如果已经存在同名节点，则合并内容
            if title in seen_titles:
                existing_node = seen_titles[title]
                existing_node.content += f"\n\n...\n\n{content}"
                continue
                
            # 创建新节点
            note_id = str(uuid.uuid4())
            seen_titles[title] = {
                "id": note_id,
                "content": content
            }
            
            # 根据分类确定节点颜色
            category = result.get("metadata", {}).get("category", "").lower()
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
