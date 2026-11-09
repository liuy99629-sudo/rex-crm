import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In dev (`npm run dev`) /api is proxied to the Laravel API. Override with VITE_API_PROXY.
const apiTarget = process.env.VITE_API_PROXY ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
  test: {
    environment: 'node',
  },
})
