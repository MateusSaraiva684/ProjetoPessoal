import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import api from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [carregandoSessao, setCarregandoSessao] = useState(() => {
    try {
      return Boolean(localStorage.getItem('access_token'))
    } catch {
      return false
    }
  })
  const [usuario, setUsuario] = useState(() => {
    try {
      const s = localStorage.getItem('usuario')
      return s ? JSON.parse(s) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    let token
    try {
      token = localStorage.getItem('access_token')
    } catch {
      setCarregandoSessao(false)
      return
    }

    if (!token) {
      setCarregandoSessao(false)
      return
    }

    api.get('/api/auth/me')
      .then(({ data }) => {
        localStorage.setItem('usuario', JSON.stringify(data))
        setUsuario(data)
      })
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('usuario')
        setUsuario(null)
      })
      .finally(() => setCarregandoSessao(false))
  }, [])

  const login = useCallback(async (email, senha) => {
    const { data } = await api.post('/api/auth/login', { email, senha }, { withCredentials: true })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('usuario', JSON.stringify(data.usuario))
    setUsuario(data.usuario)
    return data
  }, [])

  const registrar = useCallback(async (nome, email, senha) => {
    await api.post('/api/auth/registrar', { nome, email, senha })
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout', {}, { withCredentials: true })
    } catch { /* ignora erro de rede */ }
    localStorage.removeItem('access_token')
    localStorage.removeItem('usuario')
    setUsuario(null)
  }, [])

  const atualizarUsuario = useCallback((dados) => {
    setUsuario((atual) => {
      const atualizado = { ...atual, ...dados }
      localStorage.setItem('usuario', JSON.stringify(atualizado))
      return atualizado
    })
  }, [])

  return (
    <AuthContext.Provider value={{ usuario, carregandoSessao, login, registrar, logout, atualizarUsuario }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
