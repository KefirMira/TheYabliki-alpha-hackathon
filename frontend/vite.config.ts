/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    server: {
      host: '127.0.0.1',
      port: 5173,
      // Бэкенд разрешает CORS только для localhost:5173. Без strictPort Vite
      // при занятом порте тихо переезжает на 5174, и все запросы к API
      // блокируются браузером — интерфейс пишет «Сервер недоступен».
      strictPort: true,
      proxy: Object.fromEntries(
        ['/api', '/ready', '/health', '/openapi.json', '/docs'].map((path) => [
          path,
          {
            target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
            changeOrigin: false,
          },
        ])
      ),
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
  }
})
