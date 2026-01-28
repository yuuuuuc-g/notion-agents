import { useState, useCallback, useRef } from "react";

// --- 类型定义 ---
export interface Message {
  role: "user" | "assistant";
  content: string;
  audioUrl?: string;
  knowledgeContext?: {
    page_id: string;
    title: string;
    matched_snippet: string;
    score: number;
  };
}

// --- 常量配置 ---
// API_URL 仅用于拼接音频链接等静态资源，API 请求统一走相对路径
const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET;
const MODEL_NAME = "deepseek-ai/DeepSeek-V3";

export function useBioBrain(initialFileId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fileId, setFileId] = useState<string | null>(initialFileId || null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 1. 发送消息核心逻辑
  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // 乐观更新 UI
    setMessages((prev) => [...prev, { role: "user", content: query }, { role: "assistant", content: "" }]);
    setIsLoading(true);

    // 中断上一次请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      // 🔥 修复 1: 使用相对路径 /api/chat，走 Next.js 代理
      const res = await fetch(`/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${API_SECRET}`
        },
        body: JSON.stringify({
          query,
          thread_id: "react-user",
          file_id: fileId,
          model_name: MODEL_NAME
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Server returned ${res.status}: ${errText}`);
      }

      if (!res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let aiResponse = "";
      let parsedAudioUrl: string | undefined;
      let parsedMetadata: any = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunkValue = decoder.decode(value, { stream: true });
        aiResponse += chunkValue;

        // 解析音频 URL
        if (!parsedAudioUrl) {
          const audioMatch = aiResponse.match(/\[AUDIO_URL:\s*(audio_[a-f0-9]+\.mp3)\]/i);
          if (audioMatch) {
            // 这里保留 API_URL，因为是生成的静态资源链接，浏览器直接访问
            parsedAudioUrl = `${API_URL}/generated_audio/${audioMatch[1]}`;
          }
        }

        // 解析元数据
        if (!parsedMetadata) {
          const metaMatch = aiResponse.match(/\[KNOWLEDGE_META:\s*({[\s\S]*?})\]/i);
          if (metaMatch) {
            try {
              parsedMetadata = JSON.parse(metaMatch[1]);
            } catch (e) {
              // 等待数据完整
            }
          }
        }

        // 实时更新 UI
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === "assistant") {
            // 清洗内容
            let cleanContent = aiResponse
              .replace(/\[KNOWLEDGE_META:[\s\S]*?\]/g, "")
              .replace(/\[AUDIO_URL:.*?\]/g, "")
              .replace(/✅\s*(Audio generated|音频已生成).*?Path:.*?mp3/gi, "")
              .replace(/✅\s*(Audio generated|音频已生成).*?(\n|$)/gi, "")
              .trim();

            lastMsg.content = cleanContent;
            if (parsedAudioUrl) lastMsg.audioUrl = parsedAudioUrl;
            if (parsedMetadata) lastMsg.knowledgeContext = parsedMetadata;
          }
          return newMessages;
        });
      }

    } catch (error: any) {
      if (error.name === 'AbortError') return;
      console.error("Chat Error:", error);
      setMessages(prev => {
          const list = [...prev];
          if (list.length > 0 && list[list.length - 1].role === 'assistant') {
              list[list.length - 1].content += `\n\n⚠️ *Error: ${error.message}*`;
          }
          return list;
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [fileId, isLoading]);

  // 2. 文件上传逻辑
  const uploadFiles = useCallback(async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    setMessages(prev => [...prev, { role: "assistant", content: "🔄 Syncing neural context..." }]);

    try {
      // 🔥 修复 2: 使用相对路径 /api/upload
      // 原代码使用的是 ${API_URL}/upload，这会导致直接连 localhost:8000 从而 404
      // 这里的 /api/upload 会被 Next.js 代理转发到后端的 /api/upload
      const res = await fetch(`/api/upload`, {
        method: "POST",
        headers: {
          // 🔥 修复 3: 添加鉴权头 (原代码缺失)
          "Authorization": `Bearer ${API_SECRET}`
          // 注意：不要手动设置 Content-Type，fetch 会自动设置 multipart/form-data boundary
        },
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Upload failed ${res.status}: ${errText}`);
      }

      const data = await res.json();

      if (data.status === "success") {
        setFileId(data.file_id);
        setMessages(prev => {
           const list = [...prev];
           list[list.length - 1].content = `✅ **Context Synced.**\nAnalyzed ${data.file_count} files. Memory ID: \`${data.file_id.slice(0,8)}\``;
           return list;
        });
      }
    } catch (e: any) {
      console.error("Upload Error:", e);
      setMessages(prev => {
        const list = [...prev];
        list[list.length - 1].content = `❌ Context sync failed: ${e.message}`;
        return list;
     });
    }
  }, []);

  return { messages, isLoading, fileId, sendMessage, uploadFiles };
}
