import { resolve } from 'node:path'
import { pdfjsAssets } from './vite/pdfjs-assets.ts'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), pdfjsAssets(resolve(__dirname, 'node_modules/pdfjs-dist'))],
  server: {
    // VITE_API_TARGET으로 별도 백엔드 포트를 선택한다. 기본값은 8000이다.
    proxy: {
      '/api': process.env.VITE_API_TARGET || 'http://localhost:8000',
    },
  },
})
