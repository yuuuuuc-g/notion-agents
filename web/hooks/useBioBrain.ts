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
const MODEL_NAME = "deepseek-ai/DeepSeek-V3";

export function useBioBrain() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);

  // 发送消息核心逻辑
  const sendMessage = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return;

    // 1. 乐观更新 UI
    setMessages((prev) => [...prev, { role: "user", content: query }, { role: "assistant", content: "" }]);
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
      let parsedAudioUrl: string | undefined;
      let parsedMetadata: any = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunkValue = decoder.decode(value, { stream: true });
        aiResponse += chunkValue;

        // ⚡️ 优化：提取音频 URL
        if (!parsedAudioUrl) {
          const audioMatch = aiResponse.match(/\[AUDIO_URL:\s*(audio_[a-f0-9]+\.mp3)\]/i);
          if (audioMatch) {
            parsedAudioUrl = `${API_URL}/audio/${audioMatch[1]}`;
          }
        }

        // ⚡️ 优化：提取元数据
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

        // 实时更新 UI (深度清洗)
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === "assistant") {
            // 🔥 核心修改：不仅移除标签，还移除生成提示语
            let cleanContent = aiResponse
              .replace(/\[KNOWLEDGE_META:[\s\S]*?\]/g, "") // 移除元数据标签
              .replace(/\[AUDIO_URL:.*?\]/g, "")            // 移除音频标签
              .replace(/✅\s*(Audio generated|音频已生成).*?Path:.*?mp3/gi, "") // 移除英文/中文提示语
              .replace(/✅\s*(Audio generated|音频已生成).*?(\n|$)/gi, "")       // 移除简短提示
              .trim();

            lastMsg.content = cleanContent;

            if (parsedAudioUrl) lastMsg.audioUrl = parsedAudioUrl;
            if (parsedMetadata) lastMsg.knowledgeContext = parsedMetadata;
          }
          return newMessages;
        });
      }

    } catch (error) {
      console.error("Chat Error:", error);
      setMessages(prev => {
          const list = [...prev];
          if (list.length > 0 && list[list.length - 1].role === 'assistant') {
              list[list.length - 1].content += "\n\n⚠️ *Connection interrupted.*";
          }
          return list;
      });
    } finally {
      setIsLoading(false);
    }
  }, [fileId, isLoading]);

  // 文件上传逻辑
  const uploadFiles = useCallback(async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    setMessages(prev => [...prev, { role: "assistant", content: "🔄 Syncing neural context..." }]);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.status === "success") {
        setFileId(data.file_id);
        setMessages(prev => {
           const list = [...prev];
           list[list.length - 1].content = `✅ **Context Synced.**\nAnalyzed ${data.file_count} files. Memory ID: \`${data.file_id.slice(0,8)}\``;
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

  return { messages, isLoading, fileId, sendMessage, uploadFiles };
}
