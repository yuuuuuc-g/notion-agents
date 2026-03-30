import { NextRequest, NextResponse } from 'next/server';

// 1. 后端地址配置（与 chat/route 一致：本地默认 IPv4；Docker 通过 API_BASE_URL 覆盖）
const BACKEND_HOST = process.env.API_BASE_URL || 'http://127.0.0.1:8000';

export async function POST(req: NextRequest) {
  try {
    // 获取表单数据
    const formData = await req.formData();
    const rawFiles = formData.getAll('files');

    // 🔥 优雅写法回归：Node 20+ 原生支持 File 对象
    const files = rawFiles.filter((f): f is File => f instanceof File);

    if (files.length === 0) {
      return NextResponse.json(
        { error: 'No valid files provided' },
        { status: 400 }
      );
    }

    // 构建发往后端的 FormData
    const backendFormData = new FormData();
    files.forEach((file) => {
      backendFormData.append('files', file);
    });

    // 2. 拼接 API 路径
    const backendUrl = `${BACKEND_HOST}/api/upload`;
    console.log(`🔌 [UploadProxy] Forwarding ${files.length} files to: ${backendUrl}`);

    const incomingAuth = req.headers.get('authorization');
    const proxyAuth =
      incomingAuth && incomingAuth.startsWith('Bearer ')
        ? incomingAuth
        : process.env.API_SECRET
          ? `Bearer ${process.env.API_SECRET}`
          : undefined;

    if (!proxyAuth) {
      return NextResponse.json(
        {
          error:
            'Missing API authentication: set API_SECRET in web/.env.local or send Authorization: Bearer from the client',
        },
        { status: 401 }
      );
    }

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        Authorization: proxyAuth,
      },
      body: backendFormData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend upload error:', response.status, errorText);
      return NextResponse.json(
        { error: `Backend error: ${response.status} - ${errorText}` },
        { status: response.status }
      );
    }

    // 返回后端响应
    const data = await response.json();
    return NextResponse.json(data);

  } catch (error: any) {
    console.error('Upload API route error:', error);
    return NextResponse.json(
      { error: `Upload failed: ${error.message}` },
      { status: 500 }
    );
  }
}
