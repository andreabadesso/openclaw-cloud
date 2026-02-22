import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

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

export default withNextIntl(nextConfig);
