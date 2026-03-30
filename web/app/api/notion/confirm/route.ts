import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();

    // 将前端的请求打包，附带上你的专属 API_SECRET，转发给本机的 FastAPI 后端
    const backendRes = await fetch('http://127.0.0.1:8000/api/notion/confirm', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.API_SECRET}`,
      },
      body: JSON.stringify(body),
    });

    const data = await backendRes.json();

    // 如果后端不开心（比如找不到草稿），原样把错误抛给前端
    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    // 成功！返回给审批卡片
    return NextResponse.json(data);

  } catch (error) {
    console.error("Notion Confirm Proxy Error:", error);
    return NextResponse.json(
      { error: 'Failed to proxy request to python backend' },
      { status: 500 }
    );
  }
}
