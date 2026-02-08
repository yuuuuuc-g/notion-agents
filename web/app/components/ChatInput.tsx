"use client";

import { Send } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

export default function ChatInput({
  input,
  setInput,
  onSend,
  isLoading,
  textareaRef,
}: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
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
  );
}
