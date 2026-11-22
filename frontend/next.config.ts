import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The API runs separately (FastAPI). Its address comes from NEXT_PUBLIC_API_URL.
  reactStrictMode: true,
};

export default nextConfig;
