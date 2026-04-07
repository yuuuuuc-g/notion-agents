"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";

// 动态引入图谱组件，并严格禁用服务器端渲染 (SSR)
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false
});

// ===================================================================
// 类型定义
// ===================================================================

// react-force-graph-2d 底层物理引擎节点类型（与库的 NodeObject 对齐）
interface NodeObject {
  id?: string | number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
  [others: string]: unknown;
}

interface GraphNode extends NodeObject {
  id: string;
  name: string;
  color: string;
  val: number;
  content: string;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  value?: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// ===================================================================
// 主组件
// ===================================================================
export default function GraphPage() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const graphRef = useRef<any>(null);
  const clickTimeout = useRef<NodeJS.Timeout | null>(null);

  // ===================================================================
  // 获取初始图谱数据
  // ===================================================================
  const fetchGraphData = async (query: string) => {
    if (!query.trim()) {
      setGraphData({ nodes: [], links: [] });
      setSelectedNode(null);
      setExpandedNodes(new Set());
      return;
    }

    setLoading(true);
    try {
      // 通过 Next.js 代理路由转发，由服务端注入 x-api-key，避免密钥暴露到浏览器
      const response = await fetch(
        `/api/graph?q=${encodeURIComponent(query)}`
      );
      if (!response.ok) throw new Error("Network response was not ok");
      const data = await response.json();

      console.log("📊 Graph data received:", data);

      setGraphData(data);
      setSelectedNode(null);
      setExpandedNodes(new Set());

      // 自动聚焦
      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.centerAt(0, 0, 1000);
          graphRef.current.zoom(1.2, 1000);
        }
      }, 100);
    } catch (error) {
      console.error("Error fetching graph data:", error);
      alert("获取图谱数据失败，请检查后端服务");
    } finally {
      setLoading(false);
    }
  };

  // ===================================================================
  // 展开节点 - 获取相关笔记
  // ===================================================================
  const expandNode = useCallback(async (nodeId: string) => {
    if (nodeId === "center") return;

    setExpanding(true);
    try {
      // 通过 Next.js 代理路由转发，由服务端注入 x-api-key
      const response = await fetch(
        `/api/graph/expand/${nodeId}?limit=5`
      );
      if (!response.ok) throw new Error("Expand request failed");

      const newData: GraphData = await response.json();

      console.log("📂 Expansion data:", newData);

      if (newData.nodes.length === 0) {
        alert("没有找到相关笔记");
        return;
      }

      // 合并新节点和连接到现有图谱
      setGraphData((prevData) => {
        // 过滤掉已存在的节点
        const existingIds = new Set(prevData.nodes.map(n => n.id));
        const newNodes = newData.nodes.filter(n => !existingIds.has(n.id));

        // 合并
        return {
          nodes: [...prevData.nodes, ...newNodes],
          links: [...prevData.links, ...newData.links],
        };
      });

      // 标记为已展开
      setExpandedNodes(prev => new Set(prev).add(nodeId));

      console.log(`✅ Expanded ${nodeId}: +${newData.nodes.length} nodes`);
    } catch (error) {
      console.error("Error expanding node:", error);
      alert("展开节点失败");
    } finally {
      setExpanding(false);
    }
  }, []);

  // ===================================================================
  // 折叠节点 - 移除相关节点
  // ===================================================================
  const collapseNode = useCallback((nodeId: string) => {
    setGraphData((prevData) => {
      // 找出所有从 nodeId 出发的连接
      const linkedNodeIds = new Set(
        prevData.links
          .filter(link => {
            const source = typeof link.source === 'string' ? link.source : link.source.id;
            return source === nodeId;
          })
          .map(link => typeof link.target === 'string' ? link.target : link.target.id)
      );

      // 移除这些节点和相关连接
      const remainingNodes = prevData.nodes.filter(n => !linkedNodeIds.has(n.id));
      const remainingLinks = prevData.links.filter(link => {
        const source = typeof link.source === 'string' ? link.source : link.source.id;
        const target = typeof link.target === 'string' ? link.target : link.target.id;
        return !linkedNodeIds.has(source) && !linkedNodeIds.has(target);
      });

      console.log(`📁 Collapsed ${nodeId}: -${linkedNodeIds.size} nodes`);

      return {
        nodes: remainingNodes,
        links: remainingLinks,
      };
    });

    // 移除展开标记
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      newSet.delete(nodeId);
      return newSet;
    });
  }, []);

  // ===================================================================
  // 节点双击事件 - 展开/折叠
  // ===================================================================
  const handleNodeDoubleClick = useCallback((rawNode: NodeObject) => {
    const node = rawNode as GraphNode;
    console.log("🖱️🖱️ Node double-clicked:", node.name);

    if (node.id === "center") return;

    if (expandedNodes.has(node.id)) {
      // 折叠
      collapseNode(node.id);
    } else {
      // 展开
      expandNode(node.id);
    }
  }, [expandedNodes, expandNode, collapseNode]);

  // ===================================================================
  // 节点点击事件 (合并了单击与双击逻辑)
  // ===================================================================
  const handleNodeClick = useCallback((rawNode: NodeObject) => {
    const node = rawNode as GraphNode;
    if (clickTimeout.current) {
      // 💡 300毫秒内点了第二次：取消单击定时器，执行【双击】逻辑
      clearTimeout(clickTimeout.current);
      clickTimeout.current = null;
      handleNodeDoubleClick(node);
    } else {
      // 💡 第一次点击：开启 300 毫秒定时器，等待确认
      clickTimeout.current = setTimeout(() => {
        console.log("🖱️ Node clicked:", node.name);

        // 执行原有的【单击】逻辑
        if (node.id !== "center") {
          setSelectedNode(node);
          if (graphRef.current) {
            graphRef.current.centerAt(node.x ?? 0, node.y ?? 0, 1000);
          }
        }

        // 倒计时结束，清空计时器
        clickTimeout.current = null;
      }, 300);
    }
  }, [handleNodeDoubleClick]);


  // ===================================================================
  // 搜索提交
  // ===================================================================
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchGraphData(searchQuery);
  };

  // ===================================================================
  // 关闭详情面板
  // ===================================================================
  const handleCloseDetail = () => {
    setSelectedNode(null);
  };

  // ===================================================================
  // 渲染节点（自定义样式）
  // ===================================================================
  const nodeCanvasObject = useCallback((rawNode: NodeObject, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const node = rawNode as GraphNode;
    const label = node.name;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;

    // 节点圆圈
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const radius = node.val || 5;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color || "#999";
    ctx.fill();

    // 如果是选中节点，添加高亮边框
    if (selectedNode && selectedNode.id === node.id) {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 3 / globalScale;
      ctx.stroke();
    }

    // 如果是展开节点，添加脉动效果
    if (expandedNodes.has(node.id)) {
      ctx.beginPath();
      ctx.arc(x, y, radius + 3, 0, 2 * Math.PI, false);
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 2 / globalScale;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 节点标签
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, x, y + radius + fontSize);
  }, [selectedNode, expandedNodes]);

  // ===================================================================
  // 渲染
  // ===================================================================
  return (
    <div className="flex h-screen bg-gray-900">
      {/* 左侧：图谱 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部搜索栏 */}
        <div className="bg-gray-800 p-4 border-b border-gray-700">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="输入关键词搜索笔记..."
              className="flex-1 px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? "🔍 搜索中..." : "🔍 搜索"}
            </button>
          </form>

          {/* 提示信息 */}
          <div className="mt-2 text-sm text-gray-400 flex items-center gap-4">
            <span>💡 单击节点查看详情</span>
            <span>•</span>
            <span>双击节点展开/折叠相关笔记</span>
            {expanding && <span className="text-yellow-400">⏳ 展开中...</span>}
          </div>
        </div>

        {/* 图谱画布 */}
        <div className="flex-1 bg-black relative">
          {graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeCanvasObject={nodeCanvasObject}
              nodeLabel={(node: NodeObject) => `${(node as GraphNode).name}\n(双击展开)`}
              onNodeClick={handleNodeClick}
              linkColor={() => "#666"}
              linkWidth={2}
              linkDirectionalParticles={2}
              linkDirectionalParticleSpeed={0.005}
              linkDirectionalParticleWidth={2}
              d3AlphaDecay={0.02}
              d3VelocityDecay={0.3}
              warmupTicks={100}
              cooldownTicks={0}
              enableNodeDrag={true}
              enableZoomInteraction={true}
              enablePanInteraction={true}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <div className="text-6xl mb-4">🌌</div>
                <div className="text-xl mb-2">知识星图</div>
                <div className="text-sm text-gray-600">输入关键词开始探索</div>
              </div>
            </div>
          )}
        </div>

        {/* 底部状态栏 */}
        <div className="bg-gray-800 px-4 py-2 text-sm text-gray-400 border-t border-gray-700 flex items-center gap-4">
          <span>📊 节点: {graphData.nodes.length}</span>
          <span>•</span>
          <span>🔗 连接: {graphData.links.length}</span>
          <span>•</span>
          <span>📂 已展开: {expandedNodes.size}</span>
        </div>
      </div>

      {/* 右侧：详情面板 */}
      {selectedNode && (
        <div className="w-96 bg-gray-800 border-l border-gray-700 flex flex-col animate-slide-in">
          {/* 详情头部 */}
          <div className="p-4 border-b border-gray-700 flex items-start justify-between">
            <div className="flex-1 pr-2">
              <div className="flex items-center gap-2 mb-1">
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: selectedNode.color }}
                />
                <h2 className="text-lg font-semibold text-white line-clamp-2">
                  {selectedNode.name}
                </h2>
              </div>
              <div className="text-xs text-gray-400">
                ID: {selectedNode.id.slice(0, 8)}...
              </div>
            </div>
            <button
              onClick={handleCloseDetail}
              className="text-gray-400 hover:text-white p-1 transition"
              aria-label="关闭"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* 详情内容 */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-4">
              {/* 笔记内容 */}
              <div>
                <h3 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                  <span>📝</span>
                  <span>笔记内容</span>
                </h3>
                <div className="bg-gray-900 rounded-lg p-4 text-gray-300 whitespace-pre-wrap text-sm max-h-96 overflow-y-auto">
                  {selectedNode.content || "（无内容）"}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="space-y-2">
                <button
                  onClick={() => {
                    if (expandedNodes.has(selectedNode.id)) {
                      collapseNode(selectedNode.id);
                    } else {
                      expandNode(selectedNode.id);
                    }
                  }}
                  disabled={expanding}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition"
                >
                  {expanding ? (
                    "⏳ 展开中..."
                  ) : expandedNodes.has(selectedNode.id) ? (
                    "📁 折叠相关笔记"
                  ) : (
                    "📂 展开相关笔记"
                  )}
                </button>

                <button
                  onClick={() => {
                    const notionUrl = `https://www.notion.so/${selectedNode.id.replace(/-/g, "")}`;
                    window.open(notionUrl, "_blank");
                  }}
                  className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 text-sm font-medium transition"
                >
                  🔗 在 Notion 中打开
                </button>

                <button
                  onClick={() => {
                    navigator.clipboard.writeText(selectedNode.content);
                    const btn = document.activeElement as HTMLButtonElement;
                    const originalText = btn.textContent;
                    btn.textContent = "✅ 已复制";
                    setTimeout(() => {
                      btn.textContent = originalText;
                    }, 2000);
                  }}
                  className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 text-sm font-medium transition"
                >
                  📋 复制内容
                </button>
              </div>

              {/* 元数据 */}
              <div>
                <h3 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                  <span>ℹ️</span>
                  <span>元数据</span>
                </h3>
                <div className="bg-gray-900 rounded-lg p-3 text-xs text-gray-400 space-y-1">
                  <div className="flex justify-between">
                    <span>节点大小:</span>
                    <span>{selectedNode.val}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>颜色:</span>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: selectedNode.color }} />
                      <span>{selectedNode.color}</span>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <span>内容长度:</span>
                    <span>{selectedNode.content.length} 字符</span>
                  </div>
                  <div className="flex justify-between">
                    <span>展开状态:</span>
                    <span>{expandedNodes.has(selectedNode.id) ? "✅ 已展开" : "📁 未展开"}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
