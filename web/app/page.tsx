"use client";

import { useState, useRef, useEffect } from "react";
import UploadZone from "@/components/UploadZone";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

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
    setMessages((prev) => [...prev, userMsg]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const currentInput = input;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setIsLoading(true);

    try {
      // 修正 A: 接口地址从 /upload 改为 /chat
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // 修正 B: 增加 Authorization 验证（值需与后端 SETTINGS.API_SECRET 一致）
          // 建议你暂时检查后端 SETTINGS 里的 API_SECRET 是什么
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
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let aiResponse = "";

      // --- 流式读取循环 ---
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;

        // 1. 解码并累加字符串
        const chunkValue = decoder.decode(value, { stream: true });
        aiResponse += chunkValue;

        // 2. 🔍 实时正则检测：匹配后端工具返回的 [AUDIO_URL: audio_xxx.mp3]
        const audioMatch = aiResponse.match(/\[AUDIO_URL:\s*(audio_[a-f0-9]+\.mp3)\]/i);

        let audioUrl = undefined;
        if (audioMatch) {
            const filename = audioMatch[1];
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            audioUrl = `${backendUrl}/audio/${filename}`;
        }

        // 3. 实时更新 React 状态
        setMessages((prev) => {
            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];

            // 确保更新的是当前 AI 正在回复的那条消息
            if (lastMsg.role === "assistant") {
                lastMsg.content = aiResponse;

                // 核心逻辑：一旦正则匹配到 URL 且当前消息还没有绑定过 audioUrl，就赋值
                if (audioUrl && !lastMsg.audioUrl) {
                    lastMsg.audioUrl = audioUrl;
                }
            }
            return newMessages;
        });
      } // --- 循环结束 ---

    } catch (error) {
      console.error(error);
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg.role === "assistant") lastMsg.content += "\n❌ [Connection Error]";
        return newMessages;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFiles = async (files: File[]) => {
    const formData = new FormData();
    // 关键：把 "files" 改为 "file"，与后端 server.py 的 alias="file" 对齐
    files.forEach(file => formData.append("files", file));
    setMessages(prev => [...prev, { role: "assistant", content: "🔍 Reading files..." }]);

    try {
      const res = await fetch("http://localhost:8000/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.status === "success") {
        setFileId(data.file_id);
        setMessages(prev => [...prev.slice(0, -1), { role: "assistant", content: `✅ Cached ${data.file_count} files.` }]);
      } else {
        throw new Error("Upload failed");
      }
    } catch {
      setMessages(prev => [...prev.slice(0, -1), { role: "assistant", content: "❌ Upload failed." }]);
    }
  };

  return (
    <div className="flex h-screen bg-white text-gray-800 font-sans overflow-hidden">
      <style jsx global>{`
        @keyframes shine {
          to { background-position: 200% center; }
        }
        .shimmer-text {
          background: linear-gradient(to right, #134e5e, #71b280, #134e5e);
          background-size: 200% auto;
          background-clip: text;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: shine 5s linear infinite;
        }
        .prose p { margin-bottom: 0.5em; }
        .prose ul { list-style-type: disc; padding-left: 1.2em; margin-bottom: 0.5em; }
        .prose ol { list-style-type: decimal; padding-left: 1.2em; margin-bottom: 0.5em; }
        .prose strong { font-weight: 600; color: #064e3b; }
        .prose a { color: #2563eb; text-decoration: underline; cursor: pointer; }
        .prose code { background: #f3f4f6; padding: 0.2em 0.4em; rounded: 0.25em; font-size: 0.9em; font-family: monospace; }
        .user-msg .prose strong { color: #fff; }
        .user-msg .prose a { color: #dbeafe; }
      `}</style>

      {/* 🟢 左侧侧边栏 */}
      <aside
        className={`
            bg-[#f9fafb] border-r border-gray-200 flex flex-col
            transition-all duration-300 ease-in-out overflow-hidden
            ${isSidebarOpen ? 'w-80 p-6 opacity-100' : 'w-0 p-0 opacity-0'}
            hidden md:flex flex-shrink-0 z-20
        `}
      >
        <div className="mb-10 min-w-[280px]">
            <h1 className="text-4xl font-extrabold shimmer-text tracking-tight">
              Exocortex
            </h1>
            <p className="text-xs text-gray-500 mt-2 italic font-medium">
              I search, I decide, I execute.
            </p>
        </div>

        <div className="flex-1 space-y-8 min-w-[280px]">
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-gray-100">
                <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
                   🪵 Upload files
                </h3>
                <UploadZone onFilesSelected={handleFiles} isUploading={isLoading} />
            </div>

            {fileId ? (
                <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center gap-3">
                    <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse"></div>
                    <div>
                        <p className="text-sm font-bold text-emerald-800">Memory Active</p>
                        <p className="text-xs text-emerald-600 font-mono opacity-80">ID: {fileId.slice(0,6)}</p>
                    </div>
                </div>
            ) : null}

            <button
                onClick={() => window.location.reload()}
                className="w-full py-2 px-4 rounded-xl border border-gray-200 text-gray-600 text-sm hover:bg-gray-100 transition-colors flex items-center justify-center gap-2"
            >
                <span>🥀</span> Clear History
            </button>
        </div>
      </aside>

      {/* 🔵 右侧主区域 */}
      <main className="flex-1 flex flex-col h-full relative bg-white min-w-0">

        {/* 侧边栏切换按钮 */}
        <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="absolute top-4 left-4 z-30 p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
            {isSidebarOpen ? (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
            ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
            )}
        </button>

        {/* 🔥 修复核心：
            1. mx-auto: 让消息容器居中
            2. max-w-4xl: 限制最大宽度，不让消息拉太长
            3. pt-20: 顶部留白，避开左上角按钮
            4. pb-52: 底部留白，避开输入框
        */}
        <div className="flex-1 overflow-y-auto scroll-smooth">
            <div className="max-w-4xl mx-auto w-full px-4 md:px-8 pt-20 pb-52 space-y-6">

                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-[60vh] text-gray-300 space-y-4">
                        <div className="text-6xl opacity-10 grayscale">🌱</div>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`
                            max-w-[90%] md:max-w-[80%] p-4 rounded-2xl text-base leading-relaxed shadow-sm prose
                            ${msg.role === "user"
                                ? "bg-[#eff6ff] text-gray-800 rounded-br-sm user-msg"
                                : "bg-white border border-gray-100 text-gray-800 rounded-bl-sm"}
                        `}>
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                rehypePlugins={[rehypeSanitize]}
                                components={{
                                    a: ({...props}) => (
                                        <a {...props} target="_blank" rel="noopener noreferrer" />
                                    )
                                }}
                            >
                                {msg.content}
                            </ReactMarkdown>

                            {msg.audioUrl && (
                                <div className="mt-3">
                                    <audio controls src={msg.audioUrl} className="w-full h-8" />
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {isLoading && messages.length > 0 && messages[messages.length-1].role !== 'assistant' && (
                    <div className="flex justify-start">
                        <div className="bg-white p-4 rounded-2xl border border-gray-100 flex items-center gap-2">
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></span>
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                            <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
        </div>

        {/* 🔥 底部输入框容器
           1. absolute bottom-0: 固定在底部
           2. bg-gradient-to-t: 增加一个渐变遮罩，让消息滚动消失时更自然
        */}
        <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6 bg-gradient-to-t from-white via-white to-transparent z-10">
            {/* 居中限制宽度 */}
            <div className="max-w-4xl mx-auto w-full relative group">
                {/* 发光背景特效 */}
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-100 to-blue-100 rounded-[2rem] blur opacity-20 group-hover:opacity-40 transition-opacity"></div>

                <div className="relative flex items-end gap-2 bg-[#f8f9fa] border border-gray-200 rounded-[2rem] shadow-sm hover:shadow-md transition-all duration-300 p-2 pl-4 focus-within:ring-2 focus-within:ring-emerald-100 focus-within:border-emerald-200 focus-within:bg-white">
                    <textarea
                        ref={textareaRef}
                        rows={1}
                        className="flex-1 bg-transparent border-none focus:ring-0 text-gray-700 placeholder-gray-400 resize-none py-3 max-h-40 scrollbar-hide"
                        placeholder="Enter a note or topic..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isLoading}
                        style={{ minHeight: '44px' }}
                    />

                    <button
                        onClick={handleSend}
                        disabled={isLoading || !input.trim()}
                        className={`
                            mb-1 p-2 rounded-full w-10 h-10 flex items-center justify-center transition-all
                            ${input.trim()
                                ? "bg-gray-800 text-white hover:bg-black shadow-md transform hover:scale-105"
                                : "text-gray-300 cursor-not-allowed"}
                        `}
                    >
                        <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 translate-x-0.5 -translate-y-0.5">
                            <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                        </svg>
                    </button>
                </div>
            </div>
            <div className="text-center text-[10px] text-gray-300 mt-2">
                AI can make mistakes. Check important info.
            </div>
        </div>
      </main>
    </div>
  );
}
