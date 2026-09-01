import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In dev the API runs separately; in production FastAPI serves this bundle
    // itself, so the same relative /api paths work in both. Override the port
    // with API_PORT when 8000 is already taken.
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.API_PORT ?? 8000}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // MapLibre and Recharts are the two heavy dependencies and they change
        // far less often than app code; separate chunks keep them cached
        // across deploys instead of invalidating one 1.7 MB bundle.
        manualChunks: {
          maplibre: ["maplibre-gl"],
          charts: ["recharts"],
        },
      },
    },
  },
});
