import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development (npm run dev) the page talks to the Python server on port 8510; the built app is served by that server itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8510" } },
  build: { outDir: "dist", sourcemap: false },
});
