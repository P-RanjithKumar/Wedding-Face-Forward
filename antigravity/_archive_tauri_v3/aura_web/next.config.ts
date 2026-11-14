import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  // Static export only for Tauri production builds
  ...(isProd && { 
    output: "export",
    images: { unoptimized: true }
  }),

  // Proxy API requests to the FastAPI backend during development
  // Rewrites are omitted in production to comply with output: export
  ...(!isProd && {
    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    },
  }),
};

export default nextConfig;
