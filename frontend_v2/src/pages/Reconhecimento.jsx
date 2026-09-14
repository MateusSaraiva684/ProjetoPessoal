import { useEffect, useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
import Toast from '../components/Toast'
import { useAlunos } from '../hooks/useAlunos'
import { useAuth } from '../services/AuthContext'
import { identificarReconhecimentoFacial } from '../services/presencas'
import {
  RECOGNITION_CONTRACTS,
  carregarHistoricoFacialDosAlunos,
  formatarTamanho,
  getExternalIdReconhecimento,
  getSchoolIdReconhecimento,
  validarArquivoImagem,
  verificarBackendSaas,
} from '../services/reconhecimento'

function formatarData(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

function statusBadge(status) {
  if (status === 'confirmado' || status === 'success') return 'bg-success'
  if (status === 'pendente' || status === 'processing' || status === 'queued') return 'bg-warning text-dark'
  if (status === 'duplicate') return 'bg-secondary'
  return 'bg-danger'
}

function ContractRow({ label, contract }) {
  return (
    <div className="d-flex justify-content-between gap-3 py-2 border-bottom">
      <div>
        <div className="fw-medium">{label}</div>
        <div className="small text-muted">
          {contract.path ? `${contract.method} ${contract.path}` : contract.reason}
        </div>
      </div>
      <span className={`badge align-self-center ${contract.active ? 'bg-success' : 'bg-secondary'}`}>
        {contract.active ? 'confirmado' : 'indisponivel'}
      </span>
    </div>
  )
}

function StatusCard({ icon, title, status, detail, variant = 'secondary' }) {
  return (
    <div className="card shadow-sm p-3 h-100" style={{ borderRadius: 12, border: 'none' }}>
      <div className="d-flex align-items-start gap-3">
        <div className={`rounded-circle bg-${variant} bg-opacity-10 text-${variant} d-flex align-items-center justify-content-center`}
          style={{ width: 42, height: 42, minWidth: 42 }}>
          <i className={`fa ${icon}`}></i>
        </div>
        <div className="min-w-0">
          <div className="text-muted small">{title}</div>
          <div className="fw-semibold text-break">{status}</div>
          <div className="small text-muted text-break">{detail}</div>
        </div>
      </div>
    </div>
  )
}

export default function Reconhecimento() {
  const { usuario } = useAuth()
  const { alunos } = useAlunos()
  const [alunoId, setAlunoId] = useState('')
  const [arquivo, setArquivo] = useState(null)
  const [preview, setPreview] = useState('')
  const [resultado, setResultado] = useState(null)
  const [processando, setProcessando] = useState(false)
  const [erro, setErro] = useState('')
  const [backendStatus, setBackendStatus] = useState({ online: false, status: 'carregando' })
  const [historicoFacial, setHistoricoFacial] = useState([])
  const [carregandoHistorico, setCarregandoHistorico] = useState(true)

  const alunoSelecionado = useMemo(
    () => alunos.find(aluno => String(aluno.id) === String(alunoId)) || null,
    [alunos, alunoId],
  )

  const alunoReconhecido = useMemo(() => {
    if (resultado?.aluno) return resultado.aluno
    if (!resultado?.aluno_id) return null
    return alunos.find(aluno => aluno.id === resultado.aluno_id)
  }, [alunos, resultado])

  const ultimaPresenca = historicoFacial[0] || null
  const schoolId = getSchoolIdReconhecimento(alunoSelecionado, usuario)
  const externalId = getExternalIdReconhecimento(alunoSelecionado)
  const testeAtivo = usuario?.is_superuser && RECOGNITION_CONTRACTS.facialTest.active

  useEffect(() => {
    verificarBackendSaas().then(setBackendStatus)
  }, [])

  useEffect(() => {
    if (!alunos.length) {
      setHistoricoFacial([])
      setCarregandoHistorico(false)
      return
    }

    let cancelado = false
    setCarregandoHistorico(true)
    carregarHistoricoFacialDosAlunos(alunos)
      .then((data) => {
        if (!cancelado) setHistoricoFacial(data)
      })
      .finally(() => {
        if (!cancelado) setCarregandoHistorico(false)
      })
    return () => { cancelado = true }
  }, [alunos])

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  function handleArquivo(e) {
    const selecionado = e.target.files?.[0] || null
    setResultado(null)
    setErro('')

    if (!selecionado) {
      setArquivo(null)
      setPreview('')
      return
    }

    const erroValidacao = validarArquivoImagem(selecionado)
    if (erroValidacao) {
      setArquivo(null)
      setPreview('')
      e.target.value = ''
      setErro(erroValidacao)
      return
    }

    setArquivo(selecionado)
    setPreview(URL.createObjectURL(selecionado))
  }

  async function handleEnviar(e) {
    e.preventDefault()
    if (!testeAtivo) {
      setErro('Teste facial disponivel apenas para administradores.')
      return
    }
    if (!arquivo) {
      setErro('Envie uma imagem para teste.')
      return
    }

    setProcessando(true)
    setErro('')
    setResultado(null)
    try {
      const data = await identificarReconhecimentoFacial({ arquivo })
      setResultado(data)
    } catch (err) {
      setErro(err.response?.data?.detail || err.response?.data?.erro || 'Nao foi possivel processar a imagem.')
    } finally {
      setProcessando(false)
    }
  }

  function limpar() {
    setArquivo(null)
    setPreview('')
    setResultado(null)
    setErro('')
  }

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h4 className="mb-1 fw-semibold">Reconhecimento facial</h4>
            <span className="text-muted small">Operacao e diagnostico da integracao com contratos confirmados</span>
          </div>
          <button className="btn btn-outline-secondary" onClick={limpar}>
            <i className="fa fa-eraser me-1"></i>Limpar
          </button>
        </div>

        <Toast mensagem={erro} tipo="danger" onClose={() => setErro('')} />

        <div className="row g-3 mb-4">
          <div className="col-md-6 col-xl-3">
            <StatusCard
              icon="fa-server"
              title="Backend SaaS"
              status={backendStatus.online ? 'Online' : 'Indisponivel'}
              detail={backendStatus.version ? `Versao ${backendStatus.version}` : (backendStatus.error || backendStatus.status)}
              variant={backendStatus.online ? 'success' : 'danger'}
            />
          </div>
          <div className="col-md-6 col-xl-3">
            <StatusCard
              icon="fa-camera"
              title="Recognition-service"
              status="Nao exposto"
              detail={RECOGNITION_CONTRACTS.recognitionServiceStatus.reason}
            />
          </div>
          <div className="col-md-6 col-xl-3">
            <StatusCard
              icon="fa-clock"
              title="Ultima presenca facial"
              status={carregandoHistorico ? 'Carregando' : (ultimaPresenca ? formatarData(ultimaPresenca.timestamp) : 'Sem registro')}
              detail={ultimaPresenca ? ultimaPresenca.aluno?.nome : 'Obtida apenas pelo historico por aluno.'}
              variant={ultimaPresenca ? 'info' : 'secondary'}
            />
          </div>
          <div className="col-md-6 col-xl-3">
            <StatusCard
              icon="fa-triangle-exclamation"
              title="Ultima falha"
              status="Indisponivel"
              detail={RECOGNITION_CONTRACTS.integrationFailures.reason}
            />
          </div>
        </div>

        <div className="row g-3">
          <div className="col-xl-4 col-lg-5">
            <div className="card shadow-sm p-4 h-100" style={{ borderRadius: 12, border: 'none' }}>
              <h6 className="fw-semibold mb-3">
                <i className="fa fa-vial text-primary me-2"></i>Teste controlado
              </h6>

              {!usuario?.is_superuser && (
                <div className="alert alert-warning py-2 small">
                  Teste facial desabilitado para usuarios sem permissao de admin.
                </div>
              )}

              <form onSubmit={handleEnviar}>
                <div className="mb-3">
                  <label className="form-label">Aluno de referencia</label>
                  <select
                    className="form-select"
                    value={alunoId}
                    onChange={e => setAlunoId(e.target.value)}
                  >
                    <option value="">Selecione para conferir o resultado</option>
                    {alunos.map(aluno => (
                      <option key={aluno.id} value={aluno.id}>
                        {aluno.nome} - {aluno.numero_inscricao}
                      </option>
                    ))}
                  </select>
                  <div className="form-text">
                    A rota de diagnostico identifica a foto sem registrar presenca.
                  </div>
                </div>

                {alunoSelecionado && (
                  <div className="border rounded p-3 mb-3 bg-light">
                    <div className="d-flex justify-content-between gap-3 flex-wrap">
                      <div>
                        <div className="text-muted small">school_id esperado</div>
                        <div className="fw-semibold text-break">{schoolId || 'Nao disponivel'}</div>
                      </div>
                      <div>
                        <div className="text-muted small">student_id/external_id</div>
                        <div className="fw-semibold text-break">{externalId || 'Nao exposto pelo SaaS'}</div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="mb-3">
                  <label className="form-label">Foto de teste</label>
                  <input
                    type="file"
                    className="form-control"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleArquivo}
                    disabled={!testeAtivo}
                  />
                  <div className="form-text">
                    Rosto de frente, boa luz, sem oculos escuros e sem imagem borrada.
                  </div>
                </div>

                {preview && (
                  <div className="mb-3">
                    <img
                      src={preview}
                      alt="Previa da foto de teste"
                      className="w-100"
                      style={{ maxHeight: 260, objectFit: 'cover', borderRadius: 10 }}
                    />
                    <div className="small text-muted mt-1">{arquivo?.name} - {formatarTamanho(arquivo?.size)}</div>
                  </div>
                )}

                <button
                  className="btn btn-primary w-100"
                  disabled={!testeAtivo || processando || !arquivo}
                  title={!testeAtivo ? 'Endpoint ativo somente para administradores no frontend.' : undefined}
                >
                  {processando ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2"></span>Processando...
                    </>
                  ) : (
                    <>
                      <i className="fa fa-camera-retro me-1"></i>Enviar para teste facial
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>

          <div className="col-xl-8 col-lg-7">
            <div className="card shadow-sm p-4 h-100" style={{ borderRadius: 12, border: 'none' }}>
              <h6 className="fw-semibold mb-3">
                <i className="fa fa-id-badge text-primary me-2"></i>Resultado do teste
              </h6>

              {!resultado ? (
                <div className="text-center text-muted py-5">
                  <i className="fa fa-face-smile fa-3x mb-3 d-block"></i>
                  Aguardando envio de imagem.
                </div>
              ) : (
                <div className="row g-3">
                  <div className="col-md-6">
                    <div className="border rounded p-3 h-100">
                      <div className="text-muted small mb-1">Aluno reconhecido</div>
                      <div className="fw-semibold">
                        {alunoReconhecido?.nome || `ID ${resultado.aluno_id}`}
                      </div>
                      {alunoReconhecido && (
                        <div className="text-muted small">
                          {alunoReconhecido.numero_inscricao}
                          {alunoReconhecido.turma ? ` / ${alunoReconhecido.turma}` : ''}
                        </div>
                      )}
                      {alunoSelecionado && resultado.aluno_id !== alunoSelecionado.id && (
                        <div className="small text-danger mt-2">
                          Resultado diferente do aluno selecionado para conferencia.
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="col-md-6">
                    <div className="border rounded p-3 h-100">
                      <div className="text-muted small mb-1">Confianca</div>
                      <div className="fs-3 fw-semibold text-success">
                        {Math.round(resultado.confianca * 100)}%
                      </div>
                    </div>
                  </div>

                  <div className="col-12">
                    <div className="border rounded p-3">
                      <div className="d-flex justify-content-between flex-wrap gap-2">
                        <div>
                          <div className="text-muted small mb-1">Diagnostico</div>
                          <div className="fw-semibold">
                            {resultado.mensagem || 'Aluno identificado sem registrar presenca'}
                          </div>
                        </div>
                        <div className="d-flex gap-2 align-items-center flex-wrap">
                          <span className="badge bg-info text-dark">Identificacao facial</span>
                          <span className="badge bg-secondary">Sem presenca criada</span>
                          {resultado.school_id && (
                            <span className="badge bg-light text-dark border">{resultado.school_id}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="row g-3 mt-1">
          <div className="col-lg-8">
            <div className="card shadow-sm p-4" style={{ borderRadius: 12, border: 'none' }}>
              <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <h6 className="fw-semibold mb-0">
                  <i className="fa fa-clock-rotate-left text-primary me-2"></i>Historico facial
                </h6>
                <span className="badge bg-secondary fw-normal">{historicoFacial.length}</span>
              </div>

              {carregandoHistorico ? (
                <div className="text-center py-5">
                  <div className="spinner-border text-primary"></div>
                </div>
              ) : historicoFacial.length === 0 ? (
                <div className="text-center text-muted py-5">
                  <i className="fa fa-calendar-xmark fa-3x mb-3 d-block"></i>
                  Nenhuma presenca facial retornada pelos endpoints por aluno.
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-hover align-middle mb-0">
                    <thead className="table-light">
                      <tr>
                        <th>Aluno</th>
                        <th>Data/hora</th>
                        <th>Camera</th>
                        <th>Confianca</th>
                        <th>Status</th>
                        <th>Notificacao</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historicoFacial.map(presenca => (
                        <tr key={`${presenca.aluno_id}-${presenca.id}`}>
                          <td>
                            <div className="fw-medium">{presenca.aluno?.nome || `ID ${presenca.aluno_id}`}</div>
                            <div className="small text-muted">{presenca.aluno?.numero_inscricao || '-'}</div>
                          </td>
                          <td>{formatarData(presenca.timestamp)}</td>
                          <td><span className="text-muted">Nao exposta</span></td>
                          <td>
                            {typeof presenca.confianca === 'number'
                              ? `${Math.round(presenca.confianca * 100)}%`
                              : '-'}
                          </td>
                          <td>
                            <span className={`badge ${statusBadge(presenca.status)}`}>
                              {presenca.status}
                            </span>
                          </td>
                          <td><span className="badge bg-secondary">Nao exposta</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="col-lg-4">
            <div className="card shadow-sm p-4" style={{ borderRadius: 12, border: 'none' }}>
              <h6 className="fw-semibold mb-3">
                <i className="fa fa-plug text-primary me-2"></i>Mapa de endpoints
              </h6>
              <ContractRow label="Saude do SaaS" contract={RECOGNITION_CONTRACTS.backendHealth} />
              <ContractRow label="Teste facial via SaaS" contract={RECOGNITION_CONTRACTS.facialTest} />
              <ContractRow label="Historico por aluno" contract={RECOGNITION_CONTRACTS.studentPresences} />
              <ContractRow label="Webhook do recognition-service" contract={RECOGNITION_CONTRACTS.recognitionWebhook} />
              <ContractRow label="Sync manual de aluno" contract={RECOGNITION_CONTRACTS.manualStudentSync} />
              <ContractRow label="Falhas de integracao" contract={RECOGNITION_CONTRACTS.integrationFailures} />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
