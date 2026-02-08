"use client";

export default function ThinkingIndicator() {
  return (
    <div className="flex space-x-1 items-center p-2 h-6">
      <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
      <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
      <div className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce"></div>
    </div>
  );
}
