import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { AppStoreProvider } from "@/components/app-store";
import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/components/providers";
import { getProjects, getTags, getTasks, getTrashCount } from "@/lib/queries";

import "./globals.css";

/**
 * Every view reads the live database, so nothing here may be frozen at build
 * time — without this the first request after a deploy would serve whatever
 * tasks happened to exist when the bundle was compiled.
 */
export const dynamic = "force-dynamic";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Momentum", template: "%s · Momentum" },
  description: "A fast, keyboard-first todo app with natural-language scheduling.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfbfd" },
    { media: "(prefers-color-scheme: dark)", color: "#16181f" },
  ],
};

/**
 * The layout is the single place task data is loaded.
 *
 * Every view is a slice of the same list, so fetching once here means the
 * sidebar counts, the open view, and the command palette can never disagree —
 * and one `revalidatePath("/", "layout")` after a write refreshes all of them.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [tasks, projects, tags, trashCount] = await Promise.all([
    getTasks(),
    getProjects(),
    getTags(),
    getTrashCount(),
  ]);

  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body>
        <Providers>
          <AppStoreProvider tasks={tasks} projects={projects} tags={tags}>
            <AppShell trashCount={trashCount}>{children}</AppShell>
          </AppStoreProvider>
        </Providers>
      </body>
    </html>
  );
}
