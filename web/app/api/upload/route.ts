import { NextRequest, NextResponse } from 'next/server';

// Get backend URL and secret from environment variables
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const API_SECRET = process.env.API_SECRET;

if (!API_SECRET) {
  throw new Error('API_SECRET environment variable is not set in Next.js');
}

export async function POST(req: NextRequest) {
  try {
    // Get form data from the request
    const formData = await req.formData();

    // 🔒 安全的类型验证：使用 type guard 替代类型断言
    const rawFiles = formData.getAll('files');
    const files = rawFiles.filter((f): f is File => f instanceof File);
    
    if (files.length === 0) {
      return NextResponse.json(
        { error: 'No valid files provided' },
        { status: 400 }
      );
    }

    // Create a new FormData to send to backend
    const backendFormData = new FormData();
    files.forEach(file => {
      backendFormData.append('files', file);
    });

    // Prepare request to backend
    const backendUrl = `${BACKEND_URL}/upload`;
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        // Note: Don't set Content-Type for FormData, let browser set it with boundary
        'Authorization': `Bearer ${API_SECRET}`,  // Secret is now server-side only
      },
      body: backendFormData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend upload error:', response.status, errorText);
      return NextResponse.json(
        { error: `Backend error: ${response.status}` },
        { status: response.status }
      );
    }

    // Return the backend response
    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Upload API route error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
