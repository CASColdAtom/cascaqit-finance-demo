import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts/")) return "echarts";
          if (id.includes("node_modules/react")) return "react";
          if (id.includes("node_modules/lucide-react")) return "icons";
          return undefined;
        },
      },
    },
  },
});
