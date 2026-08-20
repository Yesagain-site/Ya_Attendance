import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      // Local `npm run dev` proxies to the backend; in Docker, nginx does it.
      "/api": "http://localhost:8000",
    },
  },
});
