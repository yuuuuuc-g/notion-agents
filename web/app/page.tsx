"use client";

import { useState, useRef, useEffect } from "react";
import UploadZone from "@/components/UploadZone";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import rehypeExternalLinks from 'rehype-external-links';
import {
  Sparkles, Database, ChevronLeft, Menu, Send, Zap, RefreshCw, ExternalLink, Quote
} from "lucide-react";
import { useBioBrain } from "@/hooks/useBioBrain"; // 👈 引入 Hook

export default function Home() {
  // 🔥 逻辑与视图分离
  const { messages, isLoading, fileId, sendMessage, uploadFiles } = useBioBrain();

  // UI 状态
  const [input, setInput] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动滚动
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 输入框自适应高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const onSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput(""); // 清空输入框
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="flex h-screen bg-[#fcfcfd] text-slate-800 font-sans overflow-hidden w-full relative">
      <style jsx global>{`
        @keyframes shine { to { background-position: 200% center; } }
        .shimmer-text {
          background: linear-gradient(to right, #10b981, #3b82f6, #10b981);
          background-size: 200% auto;
          background-clip: text;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: shine 6s linear infinite;
        }
        .prose p { margin-bottom: 0.8em; line-height: 1.6; }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
      `}</style>

      {/* --- SIDEBAR --- */}
      <aside className={`bg-[#0f172a] text-slate-400 flex flex-col transition-all duration-300 ease-in-out shadow-2xl z-50 ${isSidebarOpen ? 'w-80 translate-x-0 relative' : 'w-0 -translate-x-full absolute overflow-hidden'} md:flex flex-shrink-0 h-full`}>
        <div className="p-8 min-w-[320px]">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-black text-white tracking-tighter uppercase italic text-nowrap">BioBrain</h1>
          </div>
          <div className="flex items-center gap-2 mt-3 px-1">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Organic Link Active</p>
          </div>
        </div>

        <div className="flex-1 px-6 space-y-10 min-w-[320px] overflow-y-auto">
          <div className="space-y-4">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 px-1">
               <Database className="w-3.5 h-3.5" /> Memory Bank
            </label>
            <div className="bg-slate-800/40 rounded-2xl p-6 border-2 border-dashed border-slate-700/50 hover:border-emerald-500/50 hover:bg-slate-800/60 transition-all group text-center cursor-pointer">
              <UploadZone onFilesSelected={uploadFiles} isUploading={isLoading} />
            </div>
          </div>

          {fileId && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-4">
              <Zap className="w-5 h-5 text-emerald-400 fill-emerald-400/20" />
              <div className="overflow-hidden text-[11px]">
                <p className="font-bold text-emerald-400 text-nowrap">Session Active</p>
                <p className="text-emerald-500/60 font-mono truncate tracking-tight uppercase">Index: {fileId.slice(0,8)}</p>
              </div>
            </div>
          )}

          <button onClick={() => window.location.reload()} className="w-full py-3 px-4 rounded-xl border border-slate-700/50 text-slate-500 text-[11px] font-bold hover:bg-slate-800 hover:text-white transition-all flex items-center justify-center gap-2 mt-auto mb-8">
            <RefreshCw className="w-3.5 h-3.5" /> Reset Path
          </button>
        </div>
      </aside>

      {/* --- MAIN CONTENT --- */}
      <main className="flex-1 flex flex-col h-full relative bg-white min-w-0 w-full overflow-hidden">
        <div className="absolute top-4 left-4 z-[60]">
          <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 rounded-xl text-slate-400 hover:text-slate-900 hover:bg-white transition-all shadow-md bg-white border border-slate-100 flex items-center justify-center">
            {isSidebarOpen ? <ChevronLeft className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-hide pt-24 pb-48">
          <div className="max-w-3xl mx-auto w-full px-6 space-y-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-[50vh] space-y-6 text-center">
                <div className="w-30 h-30 bg-slate-50/50 rounded-[3.5rem] flex items-center justify-center shadow-inner border border-slate-100/50 animate-pulse">
                  <span className="text-5xl filter grayscale-[0.2] opacity-50">🌱</span>
                </div>
                <p className="text-slate-300 text-sm font-semibold tracking-wider italic">Input or query biobrain</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`relative max-w-[85%] md:max-w-[80%] px-6 py-4 rounded-[2rem] shadow-sm text-[15px] ${msg.role === "user" ? "bg-slate-100 text-slate-700 rounded-tr-sm" : "bg-white border border-slate-100 text-slate-700 rounded-tl-sm"}`}>
                  <div className={`text-[10px] font-black uppercase tracking-widest mb-2 opacity-40 flex items-center gap-1.5 ${msg.role === "user" ? "justify-end" : "text-emerald-600"}`}>
                    {msg.role === "assistant" && <Sparkles className="w-3 h-3" />}
                    {msg.role === "user" ? "Transmitting" : "BioBrain Intelligence"}
                  </div>

                  <div className={`prose max-w-none ${msg.role === "user" ? "prose-invert" : "prose-slate"}`}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeSanitize, [rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]]}
                      className="prose max-w-none text-slate-700"
                    >
                      {msg.content}
                    </ReactMarkdown>

                    {/* --- 💡 Qdrant Hybrid Search 高亮卡片 --- */}
                    {msg.role === "assistant" && msg.knowledgeContext && (
                      <div className="mt-6 pt-5 border-t border-slate-100 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-amber-600">
                            <Quote className="w-3.5 h-3.5 fill-amber-600/10" />
                            <span className="text-[11px] font-black uppercase tracking-wider">Notion Memory Matched</span>
                          </div>
                          <span className="text-[9px] font-mono text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">Score: {msg.knowledgeContext.score.toFixed(4)}</span>
                        </div>

                        <div className="bg-amber-50/40 rounded-2xl p-4 border border-amber-100/50 relative overflow-hidden group hover:bg-amber-50/70 transition-colors">
                          <p className="text-[13px] text-slate-600 italic leading-relaxed relative z-10">
                            “...{msg.knowledgeContext.matched_snippet}...”
                          </p>
                          <div className="mt-4 flex items-center justify-between border-t border-amber-200/30 pt-3">
                            <p className="text-[11px] font-bold text-slate-400 truncate max-w-[60%]">
                              {msg.knowledgeContext.title}
                            </p>
                            <a
                              href={`https://www.notion.so/${msg.knowledgeContext.page_id.replace(/-/g, "")}`}
                              target="_blank"
                              className="text-[11px] font-black text-amber-700 hover:text-amber-900 flex items-center gap-1 group/link"
                            >
                              Explore in Notion
                              <ExternalLink className="w-3 h-3 transition-transform group-hover/link:-translate-y-0.5 group-hover/link:translate-x-0.5" />
                            </a>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {msg.audioUrl && (
                    <div className={`mt-4 p-2 rounded-2xl ${msg.role === "user" ? "bg-slate-200" : "bg-slate-50"}`}>
                      <audio controls src={msg.audioUrl} className="w-full h-8" />
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* --- INPUT AREA --- */}
        <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-white via-white/95 to-transparent z-10">
          <div className="max-w-3xl mx-auto w-full">
            <div className="relative flex items-end gap-3 bg-[#f8f9fa] border border-slate-200 rounded-[2rem] p-2.5 pl-6 pr-2.5 shadow-sm transition-all focus-within:bg-white focus-within:shadow-xl focus-within:shadow-emerald-500/5 focus-within:border-emerald-400/40">
              <textarea
                ref={textareaRef}
                rows={1}
                className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-slate-700 caret-emerald-500 placeholder-slate-400 py-3 max-h-40 scrollbar-hide text-[15px]"
                placeholder="Let's build together..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                onClick={onSend}
                disabled={isLoading || !input.trim()}
                className={`mb-1 w-11 h-11 rounded-full flex items-center justify-center transition-all shadow-lg ${input.trim() ? "bg-slate-900 text-white hover:bg-emerald-600 active:scale-90" : "bg-slate-100 text-slate-300"}`}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <div className="text-center text-[10px] text-slate-400 mt-4 font-bold tracking-[0.3em] uppercase opacity-50">BioBrain OS // Hybrid Memory Engine v2.5</div>
          </div>
        </div>
      </main>
    </div>
  );
}
