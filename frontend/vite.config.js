import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built site works whether it's served from a domain
// root or a subdirectory.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    // In production, FastAPI serves this build and the API from the same
    // origin (see backend/app/main.py). In dev, proxy the same paths to a
    // locally-running backend so the frontend code never needs to know the
    // difference.
    proxy: {
      "/scan": "http://localhost:8001",
      "/vpat": "http://localhost:8001",
      "/issues.csv": "http://localhost:8001",
      "/health": "http://localhost:8001",
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        // Stable filenames -- no content-hash -- so deploys never break.
        entryFileNames: "scan.js",
        chunkFileNames: "scan-[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
