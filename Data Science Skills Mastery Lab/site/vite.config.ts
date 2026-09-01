import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" keeps the build portable: it works from GitHub Pages, a subfolder or file://
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", chunkSizeWarningLimit: 1200 },
});
