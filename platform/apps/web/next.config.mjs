/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@identity/shared", "@identity/api"],
  experimental: {
    serverComponentsExternalPackages: ["@prisma/client", "bcryptjs", "bullmq", "ioredis"],
  },
};

export default nextConfig;
