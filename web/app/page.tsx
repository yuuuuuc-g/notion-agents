"use client";

import { useState, useRef, useEffect } from "react";
import { useBioBrain } from "@/hooks/useBioBrain";

// 📦 Markdown 插件
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeSanitize from "rehype-sanitize";
import rehypeExternalLinks from "rehype-external-links";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";

// 💅 样式文件
import "highlight.js/styles/atom-one-dark.css";
import "katex/dist/katex.min.css";

// 组件
import Sidebar from "./components/Sidebar";
import WelcomeScreen from "./components/WelcomeScreen";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import ThinkingIndicator from "./components/ThinkingIndicator";
import { Bot } from "lucide-react";

// 全局样式
const globalStyles = `
  .scrollbar-hide::-webkit-scrollbar { display: none; }
  pre { border-radius: 0.75rem !important; margin: 1em 0 !important; }
  code { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; }
  audio::-webkit-media-controls-enclosure {
    background-color: transparent;
  }
`;

export default function Home() {
  const { messages, isLoading, fileId, sendMessage, uploadFiles } = useBioBrain();
  const [input, setInput] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // 自动调整输入框高度
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

  return (
    <div className="flex h-screen bg-[#fcfcfd] text-slate-800 font-sans overflow-hidden w-full relative">
      <style jsx global>{globalStyles}</style>

      {/* Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        fileId={fileId}
        isLoading={isLoading}
        onUpload={uploadFiles}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full relative bg-white min-w-0 w-full overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-hide pt-24 pb-48">
          <div className="max-w-3xl mx-auto w-full px-6 space-y-8">
            {/* 欢迎页面 */}
            {messages.length === 0 && <WelcomeScreen />}

            {/* 消息列表 */}
            {messages.map((msg, idx) => (
              <ChatMessage key={idx} message={msg} />
            ))}

            {/* 思考中指示器 */}
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

        {/* 输入框 */}
        <ChatInput
          input={input}
          setInput={setInput}
          onSend={onSend}
          isLoading={isLoading}
          textareaRef={textareaRef}
        />
      </main>
    </div>
  );
}
