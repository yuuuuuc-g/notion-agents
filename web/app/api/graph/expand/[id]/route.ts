import { NextRequest, NextResponse } from "next/server";

// 💡 注意这里的 params：它专门用来捕获文件夹 [id] 传来的节点 ID
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  // 服务端代理：注入 x-api-key，避免密钥暴露到浏览器
  const BACKEND_HOST = process.env.NEXT_PUBLIC_API_URL || "https://biobrain-t96m.onrender.com";
  const API_KEY = process.env.API_SECRET || "";

  // 1. 获取前端传来的 limit 参数（默认为 5）
  const limit = req.nextUrl.searchParams.get("limit") || "5";

  // 2. 🔥 核心修复：将请求转发到后端的【展开接口】，并带上 params.id
  const backendUrl = `${BACKEND_HOST}/api/graph/expand/${params.id}?limit=${limit}`;

  try {
    const res = await fetch(backendUrl, {
      headers: { "x-api-key": API_KEY }, // 依然需要带上门禁钥匙
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: `Proxy error: ${message}` }, { status: 500 });
  }
}
