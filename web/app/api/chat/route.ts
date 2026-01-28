import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  // 1. 定义后端地址
  // 在 Docker 内部，必须使用服务名 "biobrain_backend"
  // 如果环境变量没设置，默认回退到 http://biobrain_backend:8000
  const BACKEND_HOST = process.env.API_BASE_URL || 'http://biobrain_backend:8000';

  // 2. 拼接正确的 API 路径
  // 注意：后端 server.py 挂载在 /api 下，所以路径是 /api/chat
  const backendUrl = `${BACKEND_HOST}/api/chat`;

  console.log(`🔌 [NextProxy] Forwarding request to: ${backendUrl}`);

  try {
    const body = await req.json();

    // 3. 向 Python 后端发起请求
    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // 如果有 API_SECRET，加上认证头
        ...(process.env.API_SECRET ? { 'Authorization': `Bearer ${process.env.API_SECRET}` } : {}),
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
