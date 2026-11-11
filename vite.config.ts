import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Plaid's backend (api/) is served by `vercel dev` (see package.json's
    // "dev:api"), not Vite — this forwards /api/* to it so Plaid Link works
    // under `npm run dev` too, matching how Vercel routes it in production.
    proxy: {
      "/api": "http://localhost:3000",
    },
  },
});
