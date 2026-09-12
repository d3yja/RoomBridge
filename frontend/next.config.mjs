/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};
export default nextConfig;
