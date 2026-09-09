import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // PORT задаётся окружением, если 5173 занят другим проектом
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
