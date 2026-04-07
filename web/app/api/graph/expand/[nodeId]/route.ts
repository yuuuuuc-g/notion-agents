import { NextRequest, NextResponse } from "next/server";

export async function GET(
  req: NextRequest,
  { params }: { params: { nodeId: string } }
) {
  // 服务端代理：注入 x-api-key，避免密钥暴露到浏览器 bundle
  const BACKEND_HOST = process.env.API_BASE_URL || "http://127.0.0.1:8000";
  const API_KEY = process.env.API_SECRET || "";

  const limit = req.nextUrl.searchParams.get("limit") || "5";
  const backendUrl = `${BACKEND_HOST}/api/graph/expand/${params.nodeId}?limit=${limit}`;

  try {
    const res = await fetch(backendUrl, {
      headers: { "x-api-key": API_KEY },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: `Proxy error: ${message}` }, { status: 500 });
  }
}
