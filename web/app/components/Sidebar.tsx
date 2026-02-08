"use client";

import { Database, ChevronLeft, Menu, Zap, RefreshCw } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import UploadZone from "@/components/UploadZone";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  fileId: string | null;
  isLoading: boolean;
  onUpload: (files: File[]) => void;
}

export default function Sidebar({
  isOpen,
  onToggle,
  fileId,
  isLoading,
  onUpload,
}: SidebarProps) {
  return (
    <>
      {/* Sidebar */}
      <aside
        className={cn(
          "bg-[#0f172a] text-slate-400 flex flex-col transition-all duration-300 ease-in-out shadow-2xl z-50 flex-shrink-0 h-full overflow-hidden",
          isOpen ? "w-80 translate-x-0 relative" : "w-0 -translate-x-full absolute"
        )}
      >
        <div className="p-8 min-w-[320px]">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-black text-white tracking-tighter uppercase italic text-nowrap">
              BioBrain <span className="text-emerald-500 text-sm align-top">v4.0</span>
            </h1>
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
              <UploadZone onFilesSelected={onUpload} isUploading={isLoading} />
            </div>
          </div>

          {fileId && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-4 animate-in fade-in slide-in-from-left-2">
              <Zap className="w-5 h-5 text-emerald-400 fill-emerald-400/20" />
              <div className="overflow-hidden text-[11px]">
                <p className="font-bold text-emerald-400 text-nowrap">Context Loaded</p>
                <p className="text-emerald-500/60 font-mono truncate tracking-tight uppercase">
                  ID: {fileId.slice(0, 8)}
                </p>
              </div>
            </div>
          )}

          <button
            onClick={() => window.location.reload()}
            className="w-full py-3 px-4 rounded-xl border border-slate-700/50 text-slate-500 text-[11px] font-bold hover:bg-slate-800 hover:text-white transition-all flex items-center justify-center gap-2 mt-auto mb-8"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Reset Session
          </button>
        </div>
      </aside>

      {/* Toggle Button */}
      <div className="absolute top-4 left-4 z-[60]">
        <button
          onClick={onToggle}
          className="p-2 rounded-xl text-slate-400 hover:text-slate-900 hover:bg-white transition-all shadow-sm bg-white/80 backdrop-blur-sm border border-slate-200/60 flex items-center justify-center"
        >
          {isOpen ? <ChevronLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>
    </>
  );
}
