/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

// Бэкенд Django/DRF для dev-прокси.
// Story 5.1 Dev Notes: проксируем same-origin → cookie SameSite=Strict работает, CORS не нужен.
const BACKEND = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/user_login': { target: BACKEND, changeOrigin: true },
      '/logout': { target: BACKEND, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    css: false,
  },
})
