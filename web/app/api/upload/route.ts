import { NextRequest, NextResponse } from 'next/server';

// 1. 后端地址配置
const BACKEND_HOST = process.env.API_BASE_URL || 'http://biobrain_backend:8000';
const API_SECRET = process.env.API_SECRET;

if (!API_SECRET) {
  console.error('API_SECRET environment variable is not set in Next.js');
}

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

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_SECRET}`,
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
