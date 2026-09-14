import api from './api'
import { listarPresencasAluno } from './presencas'

export const MAX_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024
export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export const RECOGNITION_CONTRACTS = {
  backendHealth: {
    method: 'GET',
    path: '/api/health',
    active: true,
  },
  facialTest: {
    method: 'POST',
    path: '/api/reconhecimento/identificar',
    active: true,
  },
  studentPresences: {
    method: 'GET',
    path: '/api/presencas/aluno/{aluno_id}',
    active: true,
  },
  recognitionWebhook: {
    method: 'POST',
    path: '/api/recognition/presences',
    active: false,
    reason: 'Webhook assinado usado apenas pelo recognition-service.',
  },
  recognitionServiceStatus: {
    active: false,
    reason: 'O SaaS ainda nao expoe proxy/status do recognition-service.',
  },
  manualStudentSync: {
    active: false,
    reason: 'Nao ha endpoint SaaS para disparar sync manual de aluno.',
  },
  globalRecognitionHistory: {
    active: false,
    reason: 'Nao ha endpoint global para presencas faciais com camera/notificacao.',
  },
  integrationFailures: {
    active: false,
    reason: 'Nao ha endpoint de ultima falha de integracao.',
  },
}

export function validarArquivoImagem(arquivo) {
  if (!arquivo) return ''

  if (!IMAGE_TYPES.includes(arquivo.type)) {
    return 'Use uma imagem JPEG, PNG ou WEBP.'
  }

  if (arquivo.size > MAX_IMAGE_UPLOAD_BYTES) {
    return 'A imagem deve ter no maximo 5MB.'
  }

  return ''
}

export function formatarTamanho(bytes) {
  if (!bytes) return '0 KB'
  const mb = bytes / (1024 * 1024)
  if (mb >= 1) return `${mb.toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export function getEmpresaIdReconhecimento(aluno, usuario) {
  const value = aluno?.empresa_id ?? aluno?.user_id ?? usuario?.id
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null
}

export function getSchoolIdReconhecimento(aluno, usuario) {
  const empresaId = getEmpresaIdReconhecimento(aluno, usuario)
  return empresaId ? `escola_${empresaId}` : null
}

export function getExternalIdReconhecimento(aluno) {
  return aluno?.external_id || null
}

export function getStatusReconhecimentoAluno(aluno, usuario) {
  if (!getEmpresaIdReconhecimento(aluno, usuario)) {
    return {
      key: 'unknown',
      label: 'Status desconhecido',
      badge: 'bg-secondary',
      detail: 'Nao ha empresa_id/school_id exposto para este aluno.',
    }
  }

  if (!aluno?.foto) {
    return {
      key: 'no_photo',
      label: 'Sem foto',
      badge: 'bg-secondary',
      detail: 'Cadastre uma foto adequada antes da sincronizacao facial.',
    }
  }

  if (!getExternalIdReconhecimento(aluno)) {
    return {
      key: 'unknown',
      label: 'Status desconhecido',
      badge: 'bg-secondary',
      detail: 'Aluno ainda sem external_id para sincronizacao biometrica.',
    }
  }

  const status = String(aluno?.biometria_status || '').trim()
  const samples = Number(aluno?.face_samples_count || 0)
  const updatedAt = aluno?.biometria_atualizada_em
    ? new Date(aluno.biometria_atualizada_em).toLocaleString('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'short',
    })
    : null

  const details = {
    ready: samples > 0
      ? `${samples} amostra${samples > 1 ? 's' : ''} facial${samples > 1 ? 's' : ''}.`
      : 'Embedding facial sincronizado.',
    syncing: 'Sincronizacao biometrica em andamento.',
    retrying: 'Falha temporaria; a biometria pode ser reenviada.',
    pending: 'Aguardando sincronizacao biometrica.',
    failed: aluno?.biometria_error || 'Nao foi possivel sincronizar a biometria.',
    needs_new_photo: aluno?.biometria_error || 'A foto nao gerou uma amostra facial valida.',
    no_photo: 'Cadastre uma foto adequada antes da sincronizacao facial.',
    unknown: 'O backend nao retornou um status biometrico reconhecido.',
  }

  const map = {
    ready: { label: 'Biometria pronta', badge: 'bg-success' },
    syncing: { label: 'Sincronizando', badge: 'bg-info text-dark' },
    retrying: { label: 'Tentando novamente', badge: 'bg-warning text-dark' },
    pending: { label: 'Pendente', badge: 'bg-warning text-dark' },
    failed: { label: 'Falhou', badge: 'bg-danger' },
    needs_new_photo: { label: 'Precisa nova foto', badge: 'bg-danger' },
    no_photo: { label: 'Sem foto', badge: 'bg-secondary' },
    unknown: { label: 'Status desconhecido', badge: 'bg-secondary' },
  }

  const key = map[status] ? status : 'unknown'
  const detail = updatedAt ? `${details[key]} Atualizado em ${updatedAt}.` : details[key]
  return { key, label: map[key].label, badge: map[key].badge, detail }
}

export async function verificarBackendSaas() {
  try {
    const { data } = await api.get('/api/health')
    return {
      online: true,
      status: data?.status || 'ok',
      version: data?.version || null,
    }
  } catch (error) {
    return {
      online: false,
      status: 'indisponivel',
      error: error.response?.data?.erro || error.message,
    }
  }
}

export async function carregarHistoricoFacialDosAlunos(alunos) {
  const resultados = await Promise.all(
    alunos.map(async (aluno) => {
      try {
        const presencas = await listarPresencasAluno(aluno.id)
        return presencas.map((presenca) => ({ ...presenca, aluno }))
      } catch {
        return []
      }
    }),
  )

  return resultados
    .flat()
    .filter((presenca) => presenca.origem === 'facial')
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}
