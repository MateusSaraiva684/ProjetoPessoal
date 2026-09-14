import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'spa-fallback',
      apply: 'serve',
      configureServer(server) {
        return () => {
          server.middlewares.use((req, res, next) => {
            // Redireciona rotas desconhecidas para index.html (SPA routing)
            if (req.method === 'GET' && !req.url.includes('.')) {
              req.url = '/index.html'
            }
            next()
          })
        }
      }
    }
  ]
})
