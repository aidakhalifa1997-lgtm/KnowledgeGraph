import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, les appels /api sont relayés vers le backend FastAPI local.
// En production, c'est le serveur nginx du conteneur frontend qui assure ce relais.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: { sourcemap: false, chunkSizeWarningLimit: 900 },
});
