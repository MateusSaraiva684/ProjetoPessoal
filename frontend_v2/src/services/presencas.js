import api from './api'

export async function registrarPresencaManual(alunoId) {
  const { data } = await api.post('/api/presencas/manual', { aluno_id: alunoId })
  return data
}

export async function registrarEntrada(alunoId) {
  const { data } = await api.post('/api/presencas/entrada', { aluno_id: alunoId })
  return data
}

export async function registrarSaida(alunoId) {
  const { data } = await api.post('/api/presencas/saida', { aluno_id: alunoId })
  return data
}

export async function listarPresencasAluno(alunoId) {
  if (!alunoId) return []
  const { data } = await api.get(`/api/presencas/aluno/${alunoId}`)
  return data
}

export async function enviarReconhecimentoFacial({ arquivo, imagemBase64 }) {
  if (arquivo) {
    const formData = new FormData()
    formData.append('imagem', arquivo)
    const { data } = await api.post('/api/reconhecimento/facial', formData)
    return data
  }

  const { data } = await api.post('/api/reconhecimento/facial', {
    imagem_base64: imagemBase64,
  })
  return data
}

export async function identificarReconhecimentoFacial({ arquivo, imagemBase64 }) {
  if (arquivo) {
    const formData = new FormData()
    formData.append('file', arquivo)
    const { data } = await api.post('/api/reconhecimento/identificar', formData)
    return data
  }

  const { data } = await api.post('/api/reconhecimento/identificar', {
    imagem_base64: imagemBase64,
  })
  return data
}
