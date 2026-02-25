import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/ingestion': { target: 'http://localhost:8004', rewrite: (path) => path.replace(/^\/api\/ingestion/, '') },
      '/api/airlock': { target: 'http://localhost:8001', rewrite: (path) => path.replace(/^\/api\/airlock/, '') },
      '/api/beliefs': { target: 'http://localhost:8002', rewrite: (path) => path.replace(/^\/api\/beliefs/, '') },
      '/api/solver': { target: 'http://localhost:8003', rewrite: (path) => path.replace(/^\/api\/solver/, '') },
    }
  }
})
