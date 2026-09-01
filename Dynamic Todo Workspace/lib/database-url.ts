import path from "node:path";

/**
 * Resolve DATABASE_URL to an absolute SQLite path.
 *
 * SQLite relative paths are interpreted against the process working directory,
 * which differs between the Prisma CLI, the seed script, and the Next server —
 * an easy way to end up with two different dev.db files. Resolving to an
 * absolute path here means every entry point agrees on one database.
 *
 * Note this deliberately does NOT use `pathToFileURL`: Prisma's schema engine
 * fails to open percent-encoded paths, and this project lives under a
 * directory whose name contains spaces.
 */
export function resolveDatabaseUrl(projectRoot: string = process.cwd()): string {
  const raw = process.env.DATABASE_URL ?? "file:./prisma/dev.db";
  if (!raw.startsWith("file:")) return raw;

  const target = raw.slice("file:".length);
  const absolute = path.isAbsolute(target) ? target : path.resolve(projectRoot, target);

  return "file:" + absolute.split("\\").join("/");
}
