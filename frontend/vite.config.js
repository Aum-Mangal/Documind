import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Served from a sub-path on GitHub Pages (/<repo>/); from the root everywhere else
  base: process.env.VITE_BASE || '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    }
  }
})
