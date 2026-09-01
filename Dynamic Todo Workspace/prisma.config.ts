import path from "node:path";
import { defineConfig } from "prisma/config";
import { resolveDatabaseUrl } from "./lib/database-url";

// Prisma 7 no longer reads .env on its own.
try {
  process.loadEnvFile(path.join(import.meta.dirname, ".env"));
} catch {
  // No .env checked in / present — resolveDatabaseUrl falls back to a default.
}

export default defineConfig({
  schema: path.join("prisma", "schema.prisma"),
  datasource: {
    url: resolveDatabaseUrl(import.meta.dirname),
  },
  migrations: {
    path: path.join("prisma", "migrations"),
    seed: "tsx prisma/seed.ts",
  },
});
