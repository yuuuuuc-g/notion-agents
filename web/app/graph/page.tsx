"use client";

"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import CloseIcon from "@mui/icons-material/Close";
import SearchIcon from "@mui/icons-material/Search";
import TextField from "@mui/material/TextField";
import InputAdornment from "@mui/material/InputAdornment";
import CircularProgress from "@mui/material/CircularProgress";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export default function TopologicalGraphPage() {
  const [mounted, setMounted] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchGraphData = async (query: string) => {
    if (!query.trim()) {
      setGraphData({ nodes: [], links: [] });
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/graph?q=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error("Network response was not ok");
      const data = await response.json();
      setGraphData(data);
    } catch (error) {
      console.error("Error fetching graph data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      fetchGraphData(searchQuery);
    }
  };

  if (!mounted) {
    return <div style={{ background: "#1a1a1a", width: "100vw", height: "100vh" }} />;
  }

  return (
    <div style={{ width: "100vw", height: "100vh", background: "#1a1a1a", margin: 0, padding: 0, overflow: "hidden" }}>
      {/* Search Bar */}
      <div style={{
        position: "absolute",
        top: 20,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 100,
        width: "400px"
      }}>
        <TextField
          fullWidth
          variant="outlined"
          placeholder="Search your knowledge graph..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearch}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: "#aaa" }} />
              </InputAdornment>
            ),
            endAdornment: isLoading ? (
              <InputAdornment position="end">
                <CircularProgress size={20} sx={{ color: "#aaa" }} />
              </InputAdornment>
            ) : null,
            sx: {
              background: "#222",
              borderRadius: "4px",
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "#444",
              },
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: "#666",
              },
              "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                borderColor: "#3b82f6",
              },
              color: "#fff",
            }
          }}
        />
      </div>

      {/* Graph Canvas */}
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        nodeColor={(node: any) => node.color}
        linkColor={() => "rgba(255,255,255,0.2)"}
        onNodeClick={(node) => setSelectedNode(node)}
        nodeCanvasObject={(node, ctx, globalScale) => {
          // Draw node circle
          const label = node.name;
          const fontSize = 12 / globalScale;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.color;
          ctx.fill();

          // Draw text label
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          
          // Add text background for better readability
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); // some padding
          
          ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
          ctx.fillRect(
            node.x - bckgDimensions[0] / 2,
            node.y + 8, // Position below node
            bckgDimensions[0],
            bckgDimensions[1]
          );
          
          // Draw text
          ctx.fillStyle = '#ffffff';
          ctx.fillText(label, node.x, node.y + 8 + fontSize / 2);
        }}
      />

      {/* Node Details Drawer */}
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
          {selectedNode?.content ? (
            <div dangerouslySetInnerHTML={{ __html: selectedNode.content }} />
          ) : (
            <p>No content available for this node.</p>
          )}
        </div>
      </Drawer>
    </div>
  );
}
