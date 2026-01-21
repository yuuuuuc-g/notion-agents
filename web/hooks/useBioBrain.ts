import { useState, useCallback } from "react";

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
const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET;
const MODEL_NAME = "deepseek-ai/DeepSeek-V3"; // 保持你修改后的模型名

export function useBioBrain() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);

  // 发送消息核心逻辑
  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // 1. 乐观更新 UI
    const userMsg: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "" }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
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
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      if (!res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiResponse = "";

      // ⚡️ 性能优化：缓存已解析的数据，避免重复正则匹配
      let parsedAudioUrl: string | undefined;
      let parsedMetadata: any = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunkValue = decoder.decode(value, { stream: true });
        aiResponse += chunkValue;

        // 1. 解析音频 (一旦找到就不再重复匹配，提升性能)
        if (!parsedAudioUrl) {
          const audioMatch = aiResponse.match(/\[AUDIO_URL:\s*(audio_[a-f0-9]+\.mp3)\]/i);
          if (audioMatch) {
            parsedAudioUrl = `${API_URL}/audio/${audioMatch[1]}`;
          }
        }

        // 2. 解析元数据 (尝试解析直到成功)
        if (!parsedMetadata) {
          const metaMatch = aiResponse.match(/\[KNOWLEDGE_META:\s*({[\s\S]*?})\]/i);
          if (metaMatch) {
            try {
              parsedMetadata = JSON.parse(metaMatch[1]);
            } catch (e) {
              // JSON 不完整，等待下一块
            }
          }
        }

        // 3. 实时更新 UI
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === "assistant") {
            // 实时清理标签
            lastMsg.content = aiResponse
              .replace(/\[AUDIO_URL:.*?\]/gi, "")
              .replace(/\[KNOWLEDGE_META:.*?\]/gi, "")
              .trim();

            if (parsedAudioUrl) lastMsg.audioUrl = parsedAudioUrl;
            if (parsedMetadata) lastMsg.knowledgeContext = parsedMetadata;
          }
          return newMessages;
        });
      }

    } catch (error) {
      console.error("Chat Error:", error);
      // 可选：添加一条错误消息给用户
      setMessages(prev => [...prev, { role: "assistant", content: "⚠️ 通信中断，请重试。" }]);
    } finally {
      setIsLoading(false);
    }
  }, [fileId, isLoading]); // 依赖 fileId

  // 文件上传逻辑
  const uploadFiles = useCallback(async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    // 添加临时状态
    setMessages(prev => [...prev, { role: "assistant", content: "🔄 Syncing context..." }]);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
        // 上传接口可能不需要 Authorization，视你后端 bandwidth_limiter 而定，建议加上以防万一
        // headers: { "Authorization": `Bearer ${API_SECRET}` }
      });
      const data = await res.json();

      if (data.status === "success") {
        setFileId(data.file_id);
        setMessages(prev => {
           const list = [...prev];
           list[list.length - 1].content = "✅ Neural cache updated. Context loaded.";
           return list;
        });
      }
    } catch (e) {
      setMessages(prev => {
        const list = [...prev];
        list[list.length - 1].content = "❌ Context sync failed.";
        return list;
     });
    }
  }, []);

  return {
    messages,
    isLoading,
    fileId,
    sendMessage,
    uploadFiles
  };
}
