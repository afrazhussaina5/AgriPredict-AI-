import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies API calls to the local FastAPI backend so the
// frontend can use same-origin URLs (/api/...) and CORS stays simple.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/docs': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/openapi.json': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/redoc': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
