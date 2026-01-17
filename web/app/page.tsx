"use client";

import { useState, useRef, useEffect } from "react";
import UploadZone from "@/components/UploadZone";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import rehypeExternalLinks from 'rehype-external-links';
import {
  Trash2,
  Sparkles,
  Database,
  ChevronLeft,
  Menu,
  Send,
  Zap,
  RefreshCw
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "" }]);
    const currentInput = input;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setIsLoading(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${process.env.NEXT_PUBLIC_API_SECRET}`
        },
        body: JSON.stringify({
            query: currentInput,
            thread_id: "react-user",
            file_id: fileId,
            model_name: "deepseek/deepseek-chat"
        }),
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let aiResponse = "";

      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunkValue = decoder.decode(value, { stream: true });
          aiResponse += chunkValue;

          const audioMatch = aiResponse.match(/\[AUDIO_URL:\s*(audio_[a-f0-9]+\.mp3)\]/i);
          let audioUrl = audioMatch ? `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/audio/${audioMatch[1]}` : undefined;

          setMessages((prev) => {
              const newMessages = [...prev];
              const lastMsg = newMessages[newMessages.length - 1];
              if (lastMsg.role === "assistant") {
                  lastMsg.content = aiResponse;
                  if (audioUrl && !lastMsg.audioUrl) lastMsg.audioUrl = audioUrl;
              }
              return newMessages;
          });
        }
      }
    } catch (error) {
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleFiles = async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));
    setMessages(prev => [...prev, { role: "assistant", content: "Syncing context..." }]);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "success") {
        setFileId(data.file_id);
        setMessages(prev => [...prev.slice(0, -1), { role: "assistant", content: `Neural cache updated.` }]);
      }
    } catch {
      setMessages(prev => [...prev.slice(0, -1), { role: "assistant", content: "Context sync failed." }]);
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
      <aside
        className={`
            bg-[#0f172a] text-slate-400 flex flex-col
            transition-all duration-300 ease-in-out shadow-2xl z-50
            /* 修正点：收缩时使用 hidden 彻底释放空间，展开时使用 flex */
            ${isSidebarOpen ? 'w-80 translate-x-0 relative' : 'w-0 -translate-x-full absolute overflow-hidden'}
            md:flex flex-shrink-0 h-full
        `}
      >
        <div className="p-8 min-w-[320px]">
          <div className="flex items-center gap-4 mb-2">

            <h1 className="text-2xl font-black text-white tracking-tighter uppercase italic text-nowrap">
                BioBrain
            </h1>
          </div>
          <div className="flex items-center gap-2 mt-3 px-1">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
                Organic Link Active
            </p>
          </div>
        </div>

        <div className="flex-1 px-6 space-y-10 min-w-[320px] overflow-y-auto">
          <div className="space-y-4">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 px-1">

               <Database className="w-3.5 h-3.5" /> Memory Bank
            </label>
            <div className="bg-slate-800/40 rounded-2xl p-6 border-2 border-dashed border-slate-700/50 hover:border-emerald-500/50 hover:bg-slate-800/60 transition-all group relative overflow-hidden text-center cursor-pointer">
              <UploadZone onFilesSelected={handleFiles} isUploading={isLoading} />
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

          <button
            onClick={() => window.location.reload()}
            className="w-full py-3 px-4 rounded-xl border border-slate-700/50 text-slate-500 text-[11px] font-bold hover:bg-slate-800 hover:text-white transition-all flex items-center justify-center gap-2 mt-auto mb-8"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Reset Path
          </button>
        </div>
      </aside>

      {/* --- MAIN CONTENT --- */}
      <main className="flex-1 flex flex-col h-full relative bg-white min-w-0 w-full overflow-hidden">

        {/* Toggle Button - 现在它相对于 main 定位，确保永远不被 aside 遮挡 */}
        <div className="absolute top-4 left-4 z-[60]">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-900 hover:bg-white transition-all shadow-md bg-white border border-slate-100 flex items-center justify-center"
          >
            {isSidebarOpen ? <ChevronLeft className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto scrollbar-hide pt-24 pb-48">
          <div className="max-w-3xl mx-auto w-full px-6 space-y-8">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-[50vh] space-y-6">
                <div className="w-24 h-24 bg-slate-50/50 rounded-[2.5rem] flex items-center justify-center shadow-inner border border-slate-100/50 animate-pulse">
                  <span className="text-5xl filter grayscale-[0.2] opacity-80">🌱</span>
                </div>
                <p className="text-slate-300 text-sm font-semibold tracking-wider italic">Ready for neural input...</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`
    relative max-w-[85%] md:max-w-[80%] px-6 py-4 rounded-[2rem] shadow-sm text-[15px]
    ${msg.role === "user"
        /* 🎨 核心修改：移除 bg-[#3b82f6]，换成更柔和的颜色 */
        ? "bg-slate-100 text-slate-700 rounded-tr-sm"
        : "bg-white border border-slate-100 text-slate-700 rounded-tl-sm"}
`}>
                  <div className={`text-[10px] font-black uppercase tracking-widest mb-2 opacity-40 flex items-center gap-1.5 ${msg.role === "user" ? "justify-end" : "text-emerald-600"}`}>
                    {msg.role === "assistant" && <Sparkles className="w-3 h-3" />}
                    {msg.role === "user" ? "Transmitting" : "BioBrain Core"}
                  </div>
                  <div className={`prose max-w-none ${msg.role === "user" ? "prose-invert" : "prose-slate"}`}>
                  <ReactMarkdown
  remarkPlugins={[remarkGfm]}
  rehypePlugins={[
    rehypeSanitize,
    // 🔍 插件化解决：自动为所有链接添加 target="_blank"
    [rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
  ]}
  className="prose max-w-none text-slate-700"
>
  {msg.content}
</ReactMarkdown>
                  </div>
                  {msg.audioUrl && (
                    <div className={`mt-4 p-2 rounded-2xl ${msg.role === "user" ? "bg-blue-600/50" : "bg-slate-50"}`}>
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
            <div className="relative flex items-end gap-3 bg-[#f8f9fa] border border-slate-200 rounded-[2rem] p-2.5 pl-6 pr-2.5 shadow-sm transition-all duration-300 focus-within:bg-white focus-within:shadow-xl focus-within:shadow-emerald-500/5 focus-within:border-emerald-400/40">
              <textarea
                ref={textareaRef}
                rows={1}
                className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-slate-700 caret-emerald-500 placeholder-slate-400 py-3 max-h-40 scrollbar-hide text-[15px] selection:bg-emerald-100"
                placeholder="Message BioBrain or sync with Notion..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className={`
                    mb-1 w-11 h-11 rounded-full flex items-center justify-center transition-all shadow-lg
                    ${input.trim()
                        ? "bg-slate-900 text-white hover:bg-emerald-600 active:scale-90 shadow-emerald-500/20"
                        : "bg-slate-100 text-slate-300"}
                `}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <div className="text-center text-[10px] text-slate-400 mt-4 font-bold tracking-[0.3em] uppercase opacity-50">
              BioBrain OS // Neural Growth v2.1
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
