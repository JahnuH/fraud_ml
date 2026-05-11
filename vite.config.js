import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    proxy: {
      '/api': {
        target: 'https://aml.innovitegra.in',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api/, '/frms/behaviour'),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log(`[FRMS] ${req.method} ${req.url} → ${proxyReq.host}${proxyReq.path}`);
          });
          proxy.on('proxyRes', (proxyRes, req) => {
            console.log(`[FRMS] ${proxyRes.statusCode} ← ${req.method} ${req.url}`);
          });
          proxy.on('error', (err, req) => {
            console.error(`[FRMS] PROXY ERROR ← ${req.method} ${req.url}:`, err.message);
          });
        },
      },
    },
  },
})