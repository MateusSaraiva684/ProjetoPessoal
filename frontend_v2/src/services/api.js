import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,  // envia cookies em TODAS as requisições (necessário para cross-origin)
  timeout: 30000,  // 30 segundos de timeout
})

// ── Injeta access token em todas as requisições ───────────────────────────────
api.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  } catch (e) {
    console.warn('localStorage nao disponivel:', e)
  }
  return config
})

// ── Renovação automática do access token ao expirar ──────────────────────────
let renovando = false
let filaEspera = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthRota = original?.url?.includes('/api/auth/')
    
    // ── Tratamento específico para rate limit (429) ──────────────────────────
    if (error.response?.status === 429) {
      const retryAfter = error.response?.headers?.['retry-after'] || 60
      const errorMsg = error.response?.data?.erro || `Muitas requisições. Tente novamente em ${retryAfter}s`
      
      // Criar erro personalizado para rate limit
      const rateLimitError = new Error(errorMsg)
      rateLimitError.status = 429
      rateLimitError.retryAfter = parseInt(retryAfter)
      return Promise.reject(rateLimitError)
    }

    // ── Tratamento de token expirado (401) ──────────────────────────────────
    if (error.response?.status === 401 && !isAuthRota && !original._retry) {
      original._retry = true

      if (renovando) {
        return new Promise((resolve, reject) => {
          filaEspera.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      renovando = true

      try {
        // withCredentials já está no default da instância, mas reforçamos aqui
        const resp = await api.post('/api/auth/refresh')
        const novoToken = resp.data.access_token
        try {
          localStorage.setItem('access_token', novoToken)
        } catch (e) {
          console.warn('localStorage nao disponivel:', e)
        }

        filaEspera.forEach(({ resolve }) => resolve(novoToken))
        filaEspera = []

        original.headers.Authorization = `Bearer ${novoToken}`
        return api(original)
      } catch {
        filaEspera.forEach(({ reject }) => reject(error))
        filaEspera = []
        try {
          localStorage.removeItem('access_token')
          localStorage.removeItem('usuario')
        } catch (e) {
          console.warn('localStorage nao disponivel:', e)
        }
        const redirectTo = window.location.pathname.startsWith('/admin') ? '/admin/login' : '/'
        window.location.href = redirectTo
        return Promise.reject(error)
      } finally {
        renovando = false
      }
    }

    return Promise.reject(error)
  }
)

function resolveMediaUrl(value) {
  if (!value) return null

  try {
    return new URL(value, BASE_URL).toString()
  } catch {
    return value
  }
}

export default api
export { BASE_URL, resolveMediaUrl }
