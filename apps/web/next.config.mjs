/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL ?? "http://localhost:8000"}/:path*`,
      },
      {
        source: "/nango/:path*",
        destination: "http://nango-server:8080/:path*",
      },
    ];
  },
};

export default nextConfig;
