import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 🔥 核心配置：API 路由重写
  async rewrites() {
    return [
      {
        source: '/api/:path*', // 凡是发往 /api/xxx 的请求
        destination: 'http://127.0.0.1:8000/:path*', // 都转发给 FastAPI
      },
    ]
  },
};

export default nextConfig;