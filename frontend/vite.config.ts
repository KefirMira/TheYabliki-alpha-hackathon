/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: '::',
    port: 5173,
    // Бэкенд разрешает CORS только для localhost:5173. Без strictPort Vite
    // при занятом порте тихо переезжает на 5174, и все запросы к API
    // блокируются браузером — интерфейс пишет «Сервер недоступен».
    strictPort: true,
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    typecheck: {
      tsconfig: './tsconfig.test.json',
    },
  },
})
