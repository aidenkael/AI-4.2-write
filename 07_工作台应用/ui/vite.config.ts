import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base: './' → 构建产物可用 file:// 直接加载（pywebview 桌面壳）
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    strictPort: true,
  },
})
