import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "@prisma/client";

import { resolveDatabaseUrl } from "./database-url";

/**
 * A single Prisma client for the whole process.
 *
 * Next's dev server re-evaluates modules on every hot reload; without the
 * globalThis cache each reload would open another SQLite connection until the
 * process ran out of handles.
 */
const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

function createClient(): PrismaClient {
  const adapter = new PrismaBetterSqlite3({ url: resolveDatabaseUrl() });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });
}

export const prisma = globalForPrisma.prisma ?? createClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
