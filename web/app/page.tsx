"use client";

import { useState, useRef, useEffect } from "react";
import UploadZone from "@/components/UploadZone";
import ReactMarkdown from "react-markdown";

// 📦 Markdown 插件
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeSanitize from "rehype-sanitize";
import rehypeExternalLinks from 'rehype-external-links';
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";

// 💅 样式文件
import "highlight.js/styles/atom-one-dark.css";
import "katex/dist/katex.min.css";

import {
  Database, ChevronLeft, Menu, Send, Zap, RefreshCw, ExternalLink, Quote, ChevronDown, ChevronUp, Bot, User, Volume2
} from "lucide-react";
import { useBioBrain } from "@/hooks/useBioBrain";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- 组件：思考中动画 ---
const ThinkingIndicator = () => (
  <div className="flex space-x-1 items-center p-2 h-6">
    <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
    <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
    <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce"></div>
  </div>
);

// --- 组件：Notion 引用卡片 ---
const NotionCard = ({ context }: { context: any }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-4 border border-amber-200/60 rounded-xl overflow-hidden bg-amber-50/30 transition-all duration-300 hover:border-amber-300/80">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 bg-amber-50/50 hover:bg-amber-100/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2 text-amber-700/80">
          <Quote className="w-3.5 h-3.5" />
          <span className="text-[11px] font-bold uppercase tracking-wider">Memory Matched</span>
          <span className="text-[9px] font-mono bg-amber-200/40 px-1.5 py-0.5 rounded text-amber-800">
            {context.score.toFixed(2)}
          </span>
        </div>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-amber-500" /> : <ChevronDown className="w-3.5 h-3.5 text-amber-500" />}
      </button>

      <div className={`transition-[max-height] duration-300 ease-in-out overflow-hidden ${isOpen ? "max-h-96" : "max-h-0"}`}>
        <div className="p-4 pt-0 border-t border-amber-100/50">
           <p className="text-[13px] text-slate-600 italic leading-relaxed my-3 pl-3 border-l-2 border-amber-300/50">
             “...{context.matched_snippet}...”
           </p>
           <div className="flex items-center justify-between mt-2">
             <span className="text-[11px] font-bold text-slate-500 truncate max-w-[70%]">{context.title}</span>
             <a
               href={`https://www.notion.so/${context.page_id.replace(/-/g, "")}`}
               target="_blank"
               rel="noopener noreferrer"
               className="text-[10px] font-black text-amber-600 hover:text-amber-800 flex items-center gap-1 bg-amber-100/50 px-2 py-1 rounded-full transition-all hover:bg-amber-200/50"
             >
               Open Notion <ExternalLink className="w-2.5 h-2.5" />
             </a>
           </div>
        </div>
      </div>
    </div>
  );
};

export default function Home() {
  const { messages, isLoading, fileId, sendMessage, uploadFiles } = useBioBrain();
  const [input, setInput] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const onSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
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
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        pre { border-radius: 0.75rem !important; margin: 1em 0 !important; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; }
        audio::-webkit-media-controls-enclosure {
            background-color: transparent;
        }
      `}</style>

      {/* --- SIDEBAR --- */}
      <aside className={cn(
        // 🔥 核心修复点：添加 overflow-hidden 防止内容溢出
        "bg-[#0f172a] text-slate-400 flex flex-col transition-all duration-300 ease-in-out shadow-2xl z-50 flex-shrink-0 h-full overflow-hidden",
        isSidebarOpen ? "w-80 translate-x-0 relative" : "w-0 -translate-x-full absolute"
      )}>
        <div className="p-8 min-w-[320px]">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-black text-white tracking-tighter uppercase italic text-nowrap">BioBrain <span className="text-emerald-500 text-sm align-top">v4.0</span></h1>
          </div>
          <div className="flex items-center gap-2 mt-3 px-1">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">System Online</p>
          </div>
        </div>

        <div className="flex-1 px-6 space-y-10 min-w-[320px] overflow-y-auto">
          <div className="space-y-4">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 px-1">
               <Database className="w-3.5 h-3.5" /> Memory Injection
            </label>
            <div className="bg-slate-800/40 rounded-2xl p-6 border-2 border-dashed border-slate-700/50 hover:border-emerald-500/50 hover:bg-slate-800/60 transition-all group text-center cursor-pointer">
              <UploadZone onFilesSelected={uploadFiles} isUploading={isLoading} />
            </div>
          </div>

          {fileId && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-4 animate-in fade-in slide-in-from-left-2">
              <Zap className="w-5 h-5 text-emerald-400 fill-emerald-400/20" />
              <div className="overflow-hidden text-[11px]">
                <p className="font-bold text-emerald-400 text-nowrap">Context Loaded</p>
                <p className="text-emerald-500/60 font-mono truncate tracking-tight uppercase">ID: {fileId.slice(0,8)}</p>
              </div>
            </div>
          )}

          <button onClick={() => window.location.reload()} className="w-full py-3 px-4 rounded-xl border border-slate-700/50 text-slate-500 text-[11px] font-bold hover:bg-slate-800 hover:text-white transition-all flex items-center justify-center gap-2 mt-auto mb-8">
            <RefreshCw className="w-3.5 h-3.5" /> Reset Session
          </button>
        </div>
      </aside>

      {/* --- MAIN CONTENT --- */}
      <main className="flex-1 flex flex-col h-full relative bg-white min-w-0 w-full overflow-hidden">
        {/* Toggle Sidebar Button */}
        <div className="absolute top-4 left-4 z-[60]">
          <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 rounded-xl text-slate-400 hover:text-slate-900 hover:bg-white transition-all shadow-sm bg-white/80 backdrop-blur-sm border border-slate-200/60 flex items-center justify-center">
            {isSidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-hide pt-24 pb-48">
          <div className="max-w-3xl mx-auto w-full px-6 space-y-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-[60vh] space-y-8 text-center animate-in fade-in zoom-in duration-700">
                <div className="w-24 h-24 bg-gradient-to-tr from-slate-50 to-slate-100 rounded-[2.5rem] flex items-center justify-center shadow-lg border border-slate-100 relative overflow-hidden">
                   <div className="absolute inset-0 bg-emerald-500/5 blur-xl rounded-full"></div>
                  <span className="text-5xl filter grayscale-[0.2] opacity-80 relative z-10">🌱</span>
                </div>
                <div className="space-y-2">
                <h2 className="text-2xl font-bold tracking-tight text-slate-300">GOODGOODSTUDYDAYDAYUP</h2>
                    <p className="text-slate-100 text-sm font-medium tracking-wide">GOODGOODSTUDYDAYDAYUP</p>
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={cn("flex w-full animate-in fade-in slide-in-from-bottom-4 duration-500", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn(
                    "relative max-w-[90%] md:max-w-[85%] px-6 py-5 rounded-[2rem] shadow-sm text-[15px] leading-7 transition-all",
                    msg.role === "user"
                      ? "bg-slate-100 text-slate-800 rounded-tr-sm"
                      : "bg-white border border-slate-100 text-slate-700 rounded-tl-sm"
                )}>
                  {/* Avatar Label */}
                  <div className={cn(
                      "text-[9px] font-bold uppercase tracking-widest mb-3 flex items-center gap-2",
                      msg.role === "user" ? "text-slate-400 justify-end" : "text-emerald-600"
                  )}>
                    {msg.role === "assistant" && <Bot className="w-3.5 h-3.5" />}
                    {msg.role === "user" ? "You" : "BioBrain"}
                    {msg.role === "user" && <User className="w-3.5 h-3.5" />}
                  </div>

                  {/* Content */}
                  {msg.content && (
                    <div className="prose prose-sm max-w-none break-words prose-slate">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[
                            rehypeSanitize,
                            rehypeKatex,
                            rehypeHighlight,
                            [rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
                        ]}
                        components={{
                          code({node, className, children, ...props}) {
                             const match = /language-(\w+)/.exec(className || '')
                             return match ? (
                               <span className="relative group block my-4">
                                  <code className={`${className} rounded-lg !bg-slate-900`} {...props}>
                                    {children}
                                  </code>
                               </span>
                             ) : (
                               <code className="bg-slate-100 text-slate-800 px-1.5 py-0.5 rounded text-[0.9em] font-mono border border-slate-200" {...props}>
                                 {children}
                               </code>
                             )
                          }
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}

                  {/* Knowledge Card */}
                  {msg.role === "assistant" && msg.knowledgeContext && (
                    <NotionCard context={msg.knowledgeContext} />
                  )}

                  {/* Audio Player */}
                  {msg.audioUrl && (
                    <div className={cn(
                      "w-full flex items-center gap-3 bg-slate-50 border border-slate-200 p-3 rounded-xl",
                      msg.content ? "mt-4" : "mt-0"
                    )}>
                       <div className="w-10 h-10 bg-white border border-slate-200 rounded-full flex items-center justify-center flex-shrink-0 text-emerald-500 shadow-sm">
                          <Volume2 className="w-8 h-5" />
                       </div>
                       <audio
                         controls
                         src={msg.audioUrl}
                         className="w-full h-10 block"
                         style={{ minWidth: '200px' }}
                       />
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex w-full justify-start animate-in fade-in slide-in-from-bottom-2">
                 <div className="bg-white border border-slate-100 px-5 py-4 rounded-[2rem] rounded-tl-md shadow-sm flex items-center gap-3">
                    <Bot className="w-4 h-4 text-emerald-500/50" />
                    <ThinkingIndicator />
                 </div>
              </div>
            )}

            <div ref={messagesEndRef} className="h-4" />
          </div>
        </div>

        {/* INPUT AREA */}
        <div className="absolute bottom-0 left-0 right-0 p-6 md:p-8 bg-gradient-to-t from-white via-white/95 to-transparent z-10">
          <div className="max-w-3xl mx-auto w-full">
            <div className="relative flex items-end gap-3 bg-[#f8f9fa] border border-slate-200 rounded-[1.5rem] p-2 shadow-lg shadow-slate-200/50 transition-all focus-within:bg-white focus-within:shadow-xl focus-within:shadow-emerald-500/10 focus-within:border-emerald-500/30 group">
              <textarea
                ref={textareaRef}
                rows={1}
                className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-slate-700 caret-emerald-500 placeholder-slate-400 py-3 pl-4 max-h-40 scrollbar-hide text-[15px] resize-none"
                placeholder="Ask BioBrain anything..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                onClick={onSend}
                disabled={isLoading || !input.trim()}
                className={cn(
                    "mb-1 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200",
                    input.trim()
                        ? "bg-slate-900 text-white hover:bg-emerald-600 hover:scale-105 shadow-md"
                        : "bg-slate-200 text-slate-400 cursor-not-allowed"
                )}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <div className="text-center mt-4 flex items-center justify-center gap-2 opacity-40 hover:opacity-100 transition-opacity duration-500">
                <div className="h-px w-8 bg-slate-300"></div>
                <span className="text-[10px] text-slate-500 font-bold tracking-[0.2em] uppercase">BioBrain OS v4.2</span>
                <div className="h-px w-8 bg-slate-300"></div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
