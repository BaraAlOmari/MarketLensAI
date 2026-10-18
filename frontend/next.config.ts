import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Docker image runs a self-contained server.js with only the files it needs. Set by the
  // Dockerfile only, so local `next start` keeps working without a warning.
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
