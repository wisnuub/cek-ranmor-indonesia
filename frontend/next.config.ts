import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",          // Static HTML → Cloudflare Pages
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
