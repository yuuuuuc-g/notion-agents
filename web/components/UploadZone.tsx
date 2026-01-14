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
        relative border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer
        ${isDragOver 
          ? "border-green-500 bg-green-50 scale-[1.02]" // 拖进来时变绿、放大
          : "border-gray-300 bg-gray-50 hover:bg-gray-100" // 平时是灰色
        }
        ${isUploading ? "opacity-50 pointer-events-none" : ""}
      `}
    >
      <input
        type="file"
        multiple
        accept=".pdf,.txt,.epub,.md" // 限制格式
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        onChange={handleChange}
      />
      
      <div className="flex flex-col items-center justify-center space-y-2">
        <span className="text-4xl">📄</span>
        <p className="text-sm font-medium text-gray-600">
          {isDragOver ? "快松手，传给我！" : "点击或拖拽文件到这里"}
        </p>
        <p className="text-xs text-gray-400">支持 PDF, TXT, EPUB</p>
      </div>
    </div>
  );
}