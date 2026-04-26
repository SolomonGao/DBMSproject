import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://gdelt_backend:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://gdelt_backend:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          charts: ['echarts', 'echarts-for-react'],
          maps: ['leaflet', 'react-leaflet'],
        },
      },
    },
  },
})
