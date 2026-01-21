import { NextRequest, NextResponse } from 'next/server';

interface ChatRequest {
  query: string;
  thread_id?: string;
  file_id?: string;
  model_name?: string;
}

// Get backend URL and secret from environment variables
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const API_SECRET = process.env.API_SECRET;

if (!API_SECRET) {
  throw new Error('API_SECRET environment variable is not set in Next.js');
}

export async function POST(req: NextRequest) {
  try {
    const body: ChatRequest = await req.json();

    // Validate required fields
    if (!body.query) {
      return NextResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      );
    }

    // Prepare request to backend
    const backendUrl = `${BACKEND_URL}/chat`;
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        "Authorization": `Bearer ${process.env.API_SECRET}`,  // Secret is now server-side only
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend error:', response.status, errorText);
      return NextResponse.json(
        { error: `Backend error: ${response.status}` },
        { status: response.status }
      );
    }

    if (!response.body) {
      return NextResponse.json(
        { error: 'No response body from backend' },
        { status: 500 }
      );
    }

    // Stream the response from backend to frontend
    const reader = response.body.getReader();


    // Create a ReadableStream for the Next.js response
    const stream = new ReadableStream({
      async start(controller) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              controller.close();
              break;
            }
            controller.enqueue(value);
          }
        } catch (error) {
          console.error('Stream error:', error);
          controller.error(error);
        }
      },
    });

    return new NextResponse(stream, {
      headers: {
        'Content-Type': 'text/plain',
        'Transfer-Encoding': 'chunked',
      },
    });

  } catch (error) {
    console.error('API route error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
