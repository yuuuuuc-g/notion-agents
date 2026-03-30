import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  // 1. 定义后端地址
  // Docker 内请在环境变量中设置 API_BASE_URL=http://biobrain_backend:8000
  // 本地 npm run dev 默认使用 IPv4，避免 Node 将 localhost 解析为 ::1 而 Uvicorn 仅监听 127.0.0.1
  const BACKEND_HOST = process.env.API_BASE_URL || 'http://127.0.0.1:8000';

  // 2. 拼接正确的 API 路径
  // 注意：后端 server.py 挂载在 /api 下，所以路径是 /api/chat
  const backendUrl = `${BACKEND_HOST}/api/chat`;

  console.log(`🔌 [NextProxy] Forwarding request to: ${backendUrl}`);

  try {
    const body = await req.json();

    // 3. 转发鉴权：优先使用浏览器请求带来的 Bearer（与 useBioBrain 中 NEXT_PUBLIC_API_SECRET 一致），
    // 否则回退到服务端 API_SECRET（与根目录后端 .env 的 API_SECRET 对齐）
    const incomingAuth = req.headers.get('authorization');
    const proxyAuth =
      incomingAuth && incomingAuth.startsWith('Bearer ')
        ? incomingAuth
        : process.env.API_SECRET
          ? `Bearer ${process.env.API_SECRET}`
          : undefined;

    // 3. 向 Python 后端发起请求
    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(proxyAuth ? { Authorization: proxyAuth } : {}),
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`❌ [NextProxy] Backend Error ${res.status}: ${errorText}`);
      return NextResponse.json(
        { error: `Backend Error: ${errorText}` },
        { status: res.status }
      );
    }

    // 4. 直接透传流式响应
    return new NextResponse(res.body);

  } catch (error: any) {
    console.error('❌ [NextProxy] Connection Failed:', error);
    return NextResponse.json(
      { error: `Connection Failed: ${error.message} (Is backend running?)` },
      { status: 500 }
    );
  }
}
