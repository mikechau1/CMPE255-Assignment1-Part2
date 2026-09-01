import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the Prisma engine and its native SQLite binding out of the bundler's
  // dependency graph — they are loaded at runtime on the server only.
  serverExternalPackages: ["@prisma/client", "prisma", "better-sqlite3"],
};

export default nextConfig;
