import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend's port: 8000, as in the assignment's
// `uvicorn main:app --reload --port 8000`. Set API_PORT to use another one
// (e.g. API_PORT=8001 npm run dev, when another app already has 8000).
const API_PORT = process.env.API_PORT ?? '8000'
const API = `http://127.0.0.1:${API_PORT}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174, // 5173 is used by the Lecture 10 front end
    strictPort: true,
    // Product photos live in hw4/data/data/products, outside this folder.
    fs: { allow: ['..'] },
    // The FastAPI backend (backend/main.py) serves the API and product photos.
    proxy: {
      '/api': API,
      '/images': API,
    },
  },
})
