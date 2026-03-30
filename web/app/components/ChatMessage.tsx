"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeSanitize from "rehype-sanitize";
import rehypeExternalLinks from "rehype-external-links";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import { Bot, User, Volume2 } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import NotionCard from "./NotionCard";
import NotionApprovalCard from "./NotionApprovalCard";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface KnowledgeContext {
  page_id: string;
  title: string;
  matched_snippet: string;
  score: number;
}

interface NotionDraft {
  draft_id: string;
  title: string;
  summary: string;
  category: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
  knowledgeContext?: KnowledgeContext;
  notionDraft?: NotionDraft;
}

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  // 调试日志
  if (message.role === "assistant" && message.notionDraft) {
    console.log("🎨 [Debug] ChatMessage 收到 notionDraft:", message.notionDraft);
  }

  return (
    <div className={cn(
      "flex w-full animate-in fade-in slide-in-from-bottom-4 duration-500",
      message.role === "user" ? "justify-end" : "justify-start"
    )}>
      <div className={cn(
        "relative max-w-[90%] md:max-w-[85%] px-6 py-5 rounded-[2rem] shadow-sm text-[15px] leading-7 transition-all",
        message.role === "user"
          ? "bg-slate-100 text-slate-800 rounded-tr-sm"
          : "bg-white border border-slate-100 text-slate-700 rounded-tl-sm"
      )}>
        {/* Avatar Label */}
        <div className={cn(
          "text-[9px] font-bold uppercase tracking-widest mb-3 flex items-center gap-2",
          message.role === "user" ? "text-slate-400 justify-end" : "text-emerald-600"
        )}>
          {message.role === "assistant" && <Bot className="w-3.5 h-3.5" />}
          {message.role === "user" ? "You" : "BioBrain"}
          {message.role === "user" && <User className="w-3.5 h-3.5" />}
        </div>

        {/* Content */}
        {message.content && (
          <div className="prose prose-sm max-w-none break-words prose-slate">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[
                rehypeSanitize,
                rehypeKatex,
                rehypeHighlight,
                [rehypeExternalLinks, { target: "_blank", rel: ["noopener", "noreferrer"] }]
              ]}
              components={{
                code({ node, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
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
                  );
                }
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Knowledge Card */}
        {message.role === "assistant" && message.knowledgeContext && (
          <NotionCard context={message.knowledgeContext} />
        )}

        {/* Notion Approval Card (HITL) */}
        {message.role === "assistant" && message.notionDraft && (
          <NotionApprovalCard draft={message.notionDraft} />
        )}

        {/* Audio Player */}
        {message.audioUrl && (
          <div className={cn(
            "w-full flex items-center gap-3 bg-slate-50 border border-slate-200 p-3 rounded-xl",
            message.content ? "mt-4" : "mt-0"
          )}>
            <div className="w-10 h-10 bg-white border border-slate-200 rounded-full flex items-center justify-center flex-shrink-0 text-emerald-500 shadow-sm">
              <Volume2 className="w-8 h-5" />
            </div>
            <audio
              controls
              src={message.audioUrl}
              className="w-full h-10 block"
              style={{ minWidth: "200px" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
