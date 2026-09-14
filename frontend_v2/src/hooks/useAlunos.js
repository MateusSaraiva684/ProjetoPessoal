import { useState, useEffect, useCallback } from 'react'
import api from '../services/api'
import { useAuth } from '../services/AuthContext'

export function useAlunos({
  turma = '',
  busca = '',
  biometriaStatus = '',
  semFoto = false,
  comErroBiometria = false,
  pagina = 1,
  limite = 12,
} = {}) {
  const { usuario } = useAuth()
  const [alunos, setAlunos] = useState([])
  const [paginacao, setPaginacao] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro('')
    try {
      const params = {}
      if (turma) params.turma = turma
      if (busca.trim()) params.search = busca.trim()
      if (biometriaStatus) params.biometria_status = biometriaStatus
      if (semFoto) params.sem_foto = true
      if (comErroBiometria) params.com_erro_biometria = true
      params.page = pagina
      params.limit = limite

      const endpoint = usuario?.is_superuser
        ? '/api/admin/alunos'
        : '/api/alunos/'

      const { data } = await api.get(endpoint, { params })
      setAlunos(data.data ?? (Array.isArray(data) ? data : []))
      setPaginacao(data.paginacao ?? null)
    } catch {
      setErro('Não foi possível carregar os alunos.')
    } finally {
      setCarregando(false)
    }
  }, [turma, busca, biometriaStatus, semFoto, comErroBiometria, pagina, limite, usuario])

  useEffect(() => { carregar() }, [carregar])

  const deletar = useCallback(async (id) => {
    await api.delete(`/api/alunos/${id}`)
    setAlunos(prev => prev.filter(a => a.id !== id))
  }, [])

  return { alunos, paginacao, carregando, erro, recarregar: carregar, deletar }
}
