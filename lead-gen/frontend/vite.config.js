import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/health':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/status':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/sessions': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/history':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/download': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
