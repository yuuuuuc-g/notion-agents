"use client";

import { useState } from "react";
import { CheckCircle, XCircle, FileText, Loader2 } from "lucide-react";

interface NotionDraft {
  draft_id: string;
  title: string;
  summary: string;
  category: string;
}

interface NotionApprovalCardProps {
  draft: NotionDraft;
}

export default function NotionApprovalCard({ draft }: NotionApprovalCardProps) {
  const [status, setStatus] = useState<"pending" | "approving" | "rejecting" | "approved" | "rejected">("pending");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleConfirm = async (approved: boolean) => {
    setStatus(approved ? "approving" : "rejecting");
    setErrorMessage(null);

    try {
      const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET;

      const res = await fetch("/api/notion/confirm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${API_SECRET}`,
        },
        body: JSON.stringify({
          draft_id: draft.draft_id,
          approved,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Server returned ${res.status}: ${errText}`);
      }

      const data = await res.json();

      if (approved && data.status === "success") {
        setStatus("approved");
      } else if (!approved && data.status === "rejected") {
        setStatus("rejected");
      } else {
        throw new Error(data.message || "Unknown error");
      }
    } catch (error: any) {
      console.error("Notion Confirm Error:", error);
      setErrorMessage(error.message);
      setStatus("pending");
    }
  };

  return (
    <div className="mt-4 border border-amber-200 bg-amber-50 rounded-xl p-5 shadow-sm">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-5 h-5 text-amber-600" />
        <h3 className="text-sm font-bold text-amber-900 uppercase tracking-wide">
          Notion 写入审批
        </h3>
      </div>

      {/* 草稿信息 */}
      <div className="space-y-2 mb-4 text-sm">
        <div>
          <span className="font-semibold text-slate-700">标题：</span>
          <span className="text-slate-600">{draft.title}</span>
        </div>
        <div>
          <span className="font-semibold text-slate-700">分类：</span>
          <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-xs ml-1">
            {draft.category}
          </span>
        </div>
        <div>
          <span className="font-semibold text-slate-700">摘要：</span>
          <p className="text-slate-600 mt-1 leading-relaxed">{draft.summary}</p>
        </div>
      </div>

      {/* 错误提示 */}
      {errorMessage && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          ⚠️ {errorMessage}
        </div>
      )}

      {/* 操作按钮 */}
      {status === "pending" && (
        <div className="flex gap-3">
          <button
            onClick={() => handleConfirm(true)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            批准写入
          </button>
          <button
            onClick={() => handleConfirm(false)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg font-medium transition-colors"
          >
            <XCircle className="w-4 h-4" />
            拒绝
          </button>
        </div>
      )}

      {/* 处理中状态 */}
      {(status === "approving" || status === "rejecting") && (
        <div className="flex items-center justify-center gap-2 py-2 text-slate-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">
            {status === "approving" ? "正在写入 Notion..." : "正在取消..."}
          </span>
        </div>
      )}

      {/* 完成状态 */}
      {status === "approved" && (
        <div className="flex items-center gap-2 py-2 text-emerald-600">
          <CheckCircle className="w-5 h-5" />
          <span className="text-sm font-medium">✅ 已成功写入 Notion</span>
        </div>
      )}

      {status === "rejected" && (
        <div className="flex items-center gap-2 py-2 text-slate-500">
          <XCircle className="w-5 h-5" />
          <span className="text-sm font-medium">已取消写入</span>
        </div>
      )}
    </div>
  );
}
