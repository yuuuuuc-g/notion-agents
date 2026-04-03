"use client";

import { useState, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import CloseIcon from "@mui/icons-material/Close";

// 避坑 1：仅在客户端动态加载力导向图引擎，彻底剥离 SSR
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

// 避坑 2：必须是规范的默认导出 React 组件
export default function TopologicalGraphPage() {
  const [mounted, setMounted] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);

  // 避坑 3：防止 Next.js 水合报错 (Hydration Mismatch)
  useEffect(() => {
    setMounted(true);
  }, []);

  // 硬编码的测试数据
  const graphData = useMemo(() => ({
    nodes: [
      { id: "center", name: "检索: 动词变位", color: "#ffffff", val: 20 },
      // 西语库 (红色)
      { id: "es1", name: "Ser vs Estar", color: "#ef4444", val: 10 },
      { id: "es2", name: "Tener 用法", color: "#ef4444", val: 10 },
      // 科技库 (蓝色)
      { id: "tech1", name: "NLP 词法分析", color: "#3b82f6", val: 10 },
      { id: "tech2", name: "Qdrant 向量距离", color: "#3b82f6", val: 10 },
      // 人文库 (绿色)
      { id: "hu1", name: "语言演化规律", color: "#10b981", val: 10 },
    ],
    links: [
      { source: "center", target: "es1" },
      { source: "center", target: "es2" },
      { source: "center", target: "tech1" },
      { source: "center", target: "tech2" },
      { source: "center", target: "hu1" },
      { source: "es1", target: "hu1" }, // 跨界灵感连接
    ]
  }), []);

  // 如果还没挂载到客户端，先渲染一个黑色全屏背景占位
  if (!mounted) {
    return <div style={{ background: "#1a1a1a", width: "100vw", height: "100vh" }} />;
  }

  return (
    <div style={{ width: "100vw", height: "100vh", background: "#1a1a1a", margin: 0, padding: 0, overflow: "hidden" }}>
      {/* 核心拓扑图画布 */}
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        nodeColor={(node: any) => node.color}
        linkColor={() => "rgba(255,255,255,0.2)"}
        onNodeClick={(node) => setSelectedNode(node)}
      />

      {/* 右侧优雅的详情抽屉 */}
      <Drawer
        anchor="right"
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
        PaperProps={{
          sx: { width: 350, background: "#222", color: "#fff", padding: 3 },
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #444", paddingBottom: "10px" }}>
          <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 500 }}>
            {selectedNode?.name}
          </h2>
          <IconButton onClick={() => setSelectedNode(null)} sx={{ color: "#fff" }}>
            <CloseIcon />
          </IconButton>
        </div>
        
        <div style={{ marginTop: "20px", color: "#aaa", lineHeight: 1.6 }}>
          <p>这里是关于 <strong style={{ color: selectedNode?.color }}>{selectedNode?.name}</strong> 的详细笔记内容...</p>
          <div style={{ marginTop: "30px", padding: "15px", background: "#111", borderRadius: "8px", fontSize: "0.9rem" }}>
            (💡 未来这里将接入 Qdrant 向量数据库，并渲染真实的 Markdown 文本与 AI 对话框)
          </div>
        </div>
      </Drawer>
    </div>
  );
}