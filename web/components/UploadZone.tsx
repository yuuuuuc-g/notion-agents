"use client";

import { useState, useCallback } from "react";

// 定义组件接收的参数：父组件给我的“回调函数”
interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  isUploading: boolean;
}

export default function UploadZone({ onFilesSelected, isUploading }: UploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  // 处理拖拽进入
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault(); // 阻止浏览器默认行为（默认是打开文件）
    setIsDragOver(true);
  }, []);

  // 处理拖拽离开
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  // 处理“松手”放下文件
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      // 把 FileList 转成数组
      const filesArray = Array.from(e.dataTransfer.files);
      // 调用父组件给的函数，把文件交上去
      onFilesSelected(filesArray);
    }
  }, [onFilesSelected]);

  // 处理点击选择文件
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      onFilesSelected(filesArray);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`
        relative transition-all cursor-pointer w-full bg-transparent
        ${isDragOver ? "scale-[1.05] brightness-125" : "hover:brightness-110"}
        ${isUploading ? "opacity-30 pointer-events-none" : ""}
      `}
    >
      <input
        type="file"
        multiple
        accept=".pdf,.txt,.epub,.md"
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
        onChange={handleChange}
      />

      <div className="flex flex-col items-center justify-center space-y-1">
        <p className={`text-sm font-bold transition-colors ${isDragOver ? "text-emerald-400" : "text-slate-300"}`}>
          {isDragOver ? "Drop to upload" : "Click or drag files"}
        </p>
        <p className="text-[10px] text-slate-500 font-medium tracking-wide">
          PDF, TXT, EPUB supported
        </p>
      </div>
    </div>
  );
}
