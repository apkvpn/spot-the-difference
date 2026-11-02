import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingExcludes: {
    "*": ["./data/**/*", "./worker/**/*"],
  },
};

export default nextConfig;
