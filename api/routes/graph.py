"""
api/routes/graph.py
知识图谱 API 路由
增强版 - 支持笔记间关联和节点展开

新增功能：
1. 返回笔记之间的关联关系（相似度连接）
2. 支持获取单个节点的相关笔记（展开功能）
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from core.container import container
from utils.logger import get_logger

# 从环境变量读取密钥，本地开发回退到 dev_secret_key
_API_KEY = os.getenv("BIOBRAIN_API_KEY", "dev_secret_key")


def verify_api_key(x_api_key: str = Header(..., alias="x-api-key")) -> None:
    """校验请求头中的 x-api-key，不匹配则返回 401"""
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


logger = get_logger("biobrain.graph")

router = APIRouter()


# Pydantic 模型


class GraphNode(BaseModel):
    id: str
    name: str
    color: str
    val: int
    content: str = ""


class GraphLink(BaseModel):
    source: str
    target: str
    value: float = 1.0  # 连接强度（可选）


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


@router.get(
    "/graph", response_model=GraphResponse, dependencies=[Depends(verify_api_key)]
)
async def get_graph_data(q: Optional[str] = Query(None)):
    """获取知识图谱数据

    Args:
        q: 搜索词

    Returns:
        包含节点和连接的图谱数据
        - 中心节点：搜索查询
        - 笔记节点：搜索结果
        - 连接：中心→笔记 + 笔记间相似度连接
    """
    nodes = []
    links = []

    try:
        # 获取向量存储实例
        vector_store = container.vector_store()

        # 如果没有查询词，返回空图谱
        if not q:
            return GraphResponse(nodes=[], links=[])

        # 创建中心节点
        center_node = GraphNode(
            id="center", name=f"🔍 {q}", color="#ffffff", val=20, content=f"搜索查询: {q}"
        )
        nodes.append(center_node)

        # 搜索相关笔记
        search_results = vector_store.search_with_context(
            query=q, top_k=15, domain="All"  # 获取更多结果用于构建图谱
        )

        logger.debug(f"🔍 Search results: match={search_results.get('match', False)}")

        if not search_results.get("match", False):
            logger.info(f"   ℹ️ No matches found for query: {q}")
            return GraphResponse(nodes=[center_node], links=[])

        results_list = search_results.get("results", [])
        logger.debug(f"📊 Found {len(results_list)} results")

        # 用于去重和内容合并
        seen_pages = {}  # {page_id: GraphNode}
        page_scores = {}  # {page_id: score} 用于计算相似度

        # ===================================================================
        # 第一遍：创建所有节点
        # ===================================================================
        for result in results_list:
            page_id = result.get("page_id")
            title = result.get("title", "Untitled")
            content = result.get("full_context") or result.get("content", "")
            score = result.get("score", 0.0)

            # 提取分类信息
            metadata = result.get("metadata", {})
            category = (
                metadata.get("category", "").lower()
                if isinstance(metadata, dict)
                else ""
            )
            domain = result.get("domain") or metadata.get("domain", "")
            if isinstance(domain, str):
                domain = domain.lower()

            # 去重：如果已存在，合并内容
            if page_id in seen_pages:
                existing_node = seen_pages[page_id]
                existing_node.content += f"\n\n...\n\n{content}"
                # 更新分数（取最高）
                page_scores[page_id] = max(page_scores.get(page_id, 0), score)
                continue

            # 确定节点颜色
            color = "#aaaaaa"  # 默认灰色
            if "spanish" in category or "spanish" in domain:
                color = "#ef4444"  # 西语-红色
            elif "tech" in category or "tech" in domain:
                color = "#3b82f6"  # 技术-蓝色
            elif "humanities" in category or "humanities" in domain:
                color = "#10b981"  # 人文-绿色
            elif "general" in category or "general" in domain:
                color = "#f59e0b"  # 通用-橙色

            # 节点大小根据相关度
            val = int(10 + score * 10)  # 10-20 之间

            # 创建笔记节点
            note_node = GraphNode(
                id=page_id or str(uuid.uuid4()),
                name=title,
                color=color,
                val=val,
                content=content,
            )

            nodes.append(note_node)
            seen_pages[page_id] = note_node
            page_scores[page_id] = score

        # ===================================================================
        # 第二遍：创建连接
        # ===================================================================

        # 1. 中心节点到所有笔记的连接
        for node in nodes:
            if node.id != "center":
                link = GraphLink(
                    source="center", target=node.id, value=page_scores.get(node.id, 0.5)
                )
                links.append(link)

        # 2. 笔记之间的相似度连接
        # 策略：如果两个笔记的分数都很高（说明都相关），则连接它们
        node_list = [n for n in nodes if n.id != "center"]

        for i, node1 in enumerate(node_list):
            for node2 in node_list[i + 1 :]:
                score1 = page_scores.get(node1.id, 0)
                score2 = page_scores.get(node2.id, 0)

                # 如果两个节点都高度相关（分数 > 0.7），创建连接
                if score1 > 0.7 and score2 > 0.7:
                    # 连接强度 = 两个分数的平均值
                    link_strength = (score1 + score2) / 2

                    link = GraphLink(
                        source=node1.id, target=node2.id, value=link_strength
                    )
                    links.append(link)
                    logger.debug(
                        f"   🔗 Linked: {node1.name[:20]} <-> {node2.name[:20]} (strength: {link_strength:.2f})"
                    )

        logger.info(f"✅ Graph generated: {len(nodes)} nodes, {len(links)} links")

        return GraphResponse(nodes=nodes, links=links)

    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"无法获取图谱数据: {str(e)}")


@router.get(
    "/graph/expand/{node_id}",
    response_model=GraphResponse,
    dependencies=[Depends(verify_api_key)],
)
async def expand_node(node_id: str, limit: int = Query(5, ge=1, le=20)):
    """展开节点，获取相关笔记

    Args:
        node_id: 要展开的节点 ID（page_id）
        limit: 返回的相关笔记数量

    Returns:
        新的节点和连接（用于添加到现有图谱）
    """
    try:
        vector_store = container.vector_store()

        # 获取节点内容
        # 方法1：从 DOC_STORE 获取完整内容
        from vector.doc_store import DOC_STORE

        page_content = DOC_STORE.get_document(node_id)

        if not page_content:
            logger.warning(f"Node {node_id} not found in DOC_STORE")
            return GraphResponse(nodes=[], links=[])

        # 使用节点内容作为查询，查找相似笔记
        search_results = vector_store.search_with_context(
            query=page_content[:500],  # 使用前500字符作为查询
            top_k=limit + 1,  # +1 因为会包含自己
            domain="All",
        )

        if not search_results.get("match", False):
            return GraphResponse(nodes=[], links=[])

        results_list = search_results.get("results", [])

        # 过滤掉自己
        results_list = [r for r in results_list if r.get("page_id") != node_id][:limit]

        nodes = []
        links = []

        # 创建相关节点
        for result in results_list:
            page_id = result.get("page_id")
            title = result.get("title", "Untitled")
            content = result.get("full_context") or result.get("content", "")
            score = result.get("score", 0.0)

            # 提取分类
            metadata = result.get("metadata", {})
            category = (
                metadata.get("category", "").lower()
                if isinstance(metadata, dict)
                else ""
            )
            domain = result.get("domain") or metadata.get("domain", "")

            # 确定颜色
            color = "#aaaaaa"
            if "spanish" in str(category) or "spanish" in str(domain):
                color = "#ef4444"
            elif "tech" in str(category) or "tech" in str(domain):
                color = "#3b82f6"
            elif "humanities" in str(category) or "humanities" in str(domain):
                color = "#10b981"

            # 创建节点
            node = GraphNode(
                id=page_id,
                name=title,
                color=color,
                val=int(8 + score * 7),  # 稍小一些（8-15）
                content=content,
            )
            nodes.append(node)

            # 创建从原节点到新节点的连接
            link = GraphLink(source=node_id, target=page_id, value=score)
            links.append(link)

        logger.info(
            f"✅ Expanded node {node_id}: +{len(nodes)} nodes, +{len(links)} links"
        )

        return GraphResponse(nodes=nodes, links=links)

    except Exception as e:
        logger.error(f"展开节点失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"无法展开节点: {str(e)}")
