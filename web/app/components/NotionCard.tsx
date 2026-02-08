"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, Quote } from "lucide-react";

interface NotionContext {
  page_id: string;
  title: string;
  matched_snippet: string;
  score: number;
}

interface NotionCardProps {
  context: NotionContext;
}

export default function NotionCard({ context }: NotionCardProps) {
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
             "...{context.matched_snippet}..."
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
}
