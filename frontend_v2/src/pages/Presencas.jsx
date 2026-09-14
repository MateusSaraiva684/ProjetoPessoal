import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Toast from '../components/Toast'
import { useAlunos } from '../hooks/useAlunos'
import { listarPresencasAluno, registrarEntrada, registrarPresencaManual, registrarSaida } from '../services/presencas'
import api from '../services/api'

function formatarData(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

function origemBadge(origem) {
  if (origem === 'facial') return 'bg-info text-dark'
  return 'bg-primary'
}

function statusBadge(status) {
  if (status === 'confirmado') return 'bg-success'
  if (status === 'pendente') return 'bg-warning text-dark'
  if (status === 'duplicada' || status === 'duplicate') return 'bg-secondary'
  return 'bg-danger'
}

export default function Presencas() {
  const [searchParams] = useSearchParams()
  const { alunos, carregando } = useAlunos()
  const [alunoId, setAlunoId] = useState(searchParams.get('aluno') || '')
  const [historico, setHistorico] = useState([])
  const [carregandoHistorico, setCarregandoHistorico] = useState(false)
  const [registrando, setRegistrando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [filtroOrigem, setFiltroOrigem] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('')
  const [relatorio, setRelatorio] = useState([])
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [camera, setCamera] = useState('')
  const [carregandoRelatorio, setCarregandoRelatorio] = useState(false)

  const alunoSelecionado = useMemo(
    () => alunos.find(aluno => String(aluno.id) === String(alunoId)),
    [alunos, alunoId],
  )

  const historicoFiltrado = useMemo(() => (
    historico.filter(presenca => {
      if (filtroOrigem && presenca.origem !== filtroOrigem) return false
      if (filtroTipo && presenca.tipo_evento !== filtroTipo) return false
      return true
    })
  ), [historico, filtroOrigem, filtroTipo])

  async function carregarHistorico(id = alunoId) {
    if (!id) {
      setHistorico([])
      return
    }

    setCarregandoHistorico(true)
    setErro('')
    try {
      const data = await listarPresencasAluno(id)
      setHistorico(data)
    } catch (err) {
      setErro(err.response?.data?.detail || err.response?.data?.erro || 'Nao foi possivel carregar as presencas.')
    } finally {
      setCarregandoHistorico(false)
    }
  }

  useEffect(() => {
    carregarHistorico(alunoId)
  }, [alunoId])

  async function handleRegistrarManual() {
    if (!alunoId) {
      setErro('Selecione um aluno.')
      return
    }

    setRegistrando(true)
    setErro('')
    setSucesso('')
    try {
      await registrarPresencaManual(Number(alunoId))
      setSucesso('Presenca registrada.')
      await carregarHistorico(alunoId)
    } catch (err) {
      setErro(err.response?.data?.detail || err.response?.data?.erro || 'Erro ao registrar presenca.')
    } finally {
      setRegistrando(false)
    }
  }

  async function carregarRelatorio() {
    setCarregandoRelatorio(true)
    setErro('')
    try {
      const params = {}
      if (alunoId) params.aluno_id = alunoId
      if (inicio) params.inicio = `${inicio}T00:00:00Z`
      if (fim) params.fim = `${fim}T23:59:59Z`
      if (camera.trim()) params.camera_id = camera.trim()
      const { data } = await api.get('/api/presencas', { params })
      setRelatorio(data || [])
    } catch (err) {
      setErro(err.response?.data?.erro || err.response?.data?.detail || 'Nao foi possivel carregar o relatorio.')
    } finally {
      setCarregandoRelatorio(false)
    }
  }

  async function exportarCsv() {
    setErro('')
    try {
      const params = {}
      if (alunoId) params.aluno_id = alunoId
      if (inicio) params.inicio = `${inicio}T00:00:00Z`
      if (fim) params.fim = `${fim}T23:59:59Z`
      if (camera.trim()) params.camera_id = camera.trim()
      const { data } = await api.get('/api/presencas/export.csv', { params, responseType: 'blob' })
      const url = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'presencas.csv'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setErro(err.response?.data?.erro || err.response?.data?.detail || 'Nao foi possivel exportar o relatorio.')
    }
  }

  async function handleRegistrar(tipo) {
    if (!alunoId) {
      setErro('Selecione um aluno.')
      return
    }

    setRegistrando(true)
    setErro('')
    setSucesso('')
    try {
      if (tipo === 'saida') {
        await registrarSaida(Number(alunoId))
        setSucesso('Saida registrada.')
      } else {
        await registrarEntrada(Number(alunoId))
        setSucesso('Entrada registrada.')
      }
      await carregarHistorico(alunoId)
    } catch (err) {
      setErro(err.response?.data?.detail || err.response?.data?.erro || 'Erro ao registrar presenca.')
    } finally {
      setRegistrando(false)
    }
  }

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h4 className="mb-1 fw-semibold">Presencas</h4>
            <span className="text-muted small">Registro manual e historico por aluno</span>
          </div>

          <div className="card shadow-sm p-3 mb-3" style={{ borderRadius: 12, border: 'none' }}>
            <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
              <h6 className="mb-0 fw-semibold"><i className="fa fa-chart-column text-primary me-2"></i>Relatório de presenças</h6>
              <div className="d-flex gap-2">
                <button className="btn btn-outline-primary btn-sm" onClick={carregarRelatorio} disabled={carregandoRelatorio}>Filtrar</button>
                <button className="btn btn-outline-success btn-sm" onClick={exportarCsv}><i className="fa fa-download me-1"></i>CSV</button>
              </div>
            </div>
            <div className="row g-2">
              <div className="col-md-3"><label className="form-label small">De</label><input type="date" className="form-control" value={inicio} onChange={e => setInicio(e.target.value)} /></div>
              <div className="col-md-3"><label className="form-label small">Até</label><input type="date" className="form-control" value={fim} onChange={e => setFim(e.target.value)} /></div>
              <div className="col-md-3"><label className="form-label small">Câmera</label><input className="form-control" placeholder="ID da câmera" value={camera} onChange={e => setCamera(e.target.value)} /></div>
              <div className="col-md-3 d-flex align-items-end"><span className="text-muted small">Filtros aplicados ao aluno selecionado e ao período informado.</span></div>
            </div>
            {relatorio.length > 0 && (
              <div className="table-responsive mt-3">
                <table className="table table-sm align-middle mb-0">
                  <thead><tr><th>Data</th><th>Aluno</th><th>Evento</th><th>Origem</th><th>Câmera</th><th>Status</th></tr></thead>
                  <tbody>{relatorio.map(item => <tr key={item.id}><td>{formatarData(item.timestamp)}</td><td>{item.aluno_id}</td><td>{item.tipo_evento}</td><td>{item.origem}</td><td>{item.camera_id || '-'}</td><td><span className={`badge ${statusBadge(item.status)}`}>{item.status}</span></td></tr>)}</tbody>
                </table>
              </div>
            )}
          </div>
          <button
            className="btn btn-outline-primary"
            onClick={() => carregarHistorico()}
            disabled={!alunoId || carregandoHistorico}
          >
            <i className="fa fa-rotate me-1"></i>Atualizar
          </button>
        </div>

        <Toast mensagem={erro} tipo="danger" onClose={() => setErro('')} />
        <Toast mensagem={sucesso} tipo="success" onClose={() => setSucesso('')} />

        <div className="row g-3">
          <div className="col-lg-4">
            <div className="card shadow-sm p-4 h-100" style={{ borderRadius: 12, border: 'none' }}>
              <h6 className="fw-semibold mb-3">
                <i className="fa fa-clipboard-check text-primary me-2"></i>Registro manual
              </h6>

              <div className="mb-3">
                <label className="form-label">Aluno</label>
                <select
                  className="form-select"
                  value={alunoId}
                  onChange={e => setAlunoId(e.target.value)}
                  disabled={carregando}
                >
                  <option value="">Selecione um aluno</option>
                  {alunos.map(aluno => (
                    <option key={aluno.id} value={aluno.id}>
                      {aluno.nome} - {aluno.numero_inscricao}
                    </option>
                  ))}
                </select>
              </div>

              {alunoSelecionado && (
                <div className="border rounded p-3 mb-3 bg-light">
                  <div className="fw-semibold">{alunoSelecionado.nome}</div>
                  <div className="text-muted small">
                    {alunoSelecionado.numero_inscricao}
                    {alunoSelecionado.turma ? ` / ${alunoSelecionado.turma}` : ''}
                  </div>
                </div>
              )}

              <div className="d-grid gap-2">
                <button className="btn btn-success" onClick={() => handleRegistrar('entrada')} disabled={!alunoId || registrando}>
                  <i className="fa fa-right-to-bracket me-1"></i>Registrar entrada
                </button>
                <button className="btn btn-outline-success" onClick={() => handleRegistrar('saida')} disabled={!alunoId || registrando}>
                  <i className="fa fa-right-from-bracket me-1"></i>Registrar saida
                </button>
                <button className="btn btn-outline-primary" onClick={handleRegistrarManual} disabled={!alunoId || registrando}>
                  {registrando ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="fa fa-pen me-1"></i>}
                  Registro manual
                </button>
              </div>
            </div>
          </div>

          <div className="col-lg-8">
            <div className="card shadow-sm p-4" style={{ borderRadius: 12, border: 'none' }}>
              <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <h6 className="fw-semibold mb-0">
                  <i className="fa fa-clock-rotate-left text-primary me-2"></i>Historico
                </h6>
                <div className="d-flex align-items-center gap-3 flex-wrap">
                  <select className="form-select form-select-sm w-auto" value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)}>
                    <option value="">Entrada e saida</option>
                    <option value="entrada">Entrada</option>
                    <option value="saida">Saida</option>
                    <option value="manual">Manual</option>
                  </select>
                  <select className="form-select form-select-sm w-auto" value={filtroOrigem} onChange={e => setFiltroOrigem(e.target.value)}>
                    <option value="">Todas origens</option>
                    <option value="manual">Manual</option>
                    <option value="facial">Facial</option>
                    <option value="webhook">Webhook</option>
                  </select>
                  <span className="badge bg-secondary fw-normal">{historicoFiltrado.length}</span>
                </div>
              </div>

              {!alunoId ? (
                <div className="text-center text-muted py-5">
                  <i className="fa fa-user-check fa-3x mb-3 d-block"></i>
                  Selecione um aluno para ver as presencas.
                </div>
              ) : carregandoHistorico ? (
                <div className="text-center py-5">
                  <div className="spinner-border text-primary"></div>
                </div>
              ) : historicoFiltrado.length === 0 ? (
                <div className="text-center text-muted py-5">
                  <i className="fa fa-calendar-xmark fa-3x mb-3 d-block"></i>
                  Nenhuma presenca registrada para o filtro atual.
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-hover align-middle mb-0">
                    <thead className="table-light">
                      <tr>
                        <th>Aluno</th>
                        <th>Evento</th>
                        <th>Data</th>
                        <th>Origem</th>
                        <th>Camera</th>
                        <th>Status</th>
                        <th>Confianca</th>
                        <th>Notificacao</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historicoFiltrado.map(presenca => (
                        <tr key={presenca.id}>
                          <td>
                            <div className="fw-medium">{alunoSelecionado?.nome || `ID ${presenca.aluno_id}`}</div>
                            <div className="small text-muted">{alunoSelecionado?.numero_inscricao || '-'}</div>
                          </td>
                          <td>
                            <span className={`badge ${presenca.tipo_evento === 'saida' ? 'bg-warning text-dark' : 'bg-success'}`}>
                              {presenca.tipo_evento || 'entrada'}
                            </span>
                          </td>
                          <td>{formatarData(presenca.timestamp)}</td>
                          <td>
                            <span className={`badge ${origemBadge(presenca.origem)}`}>
                              {presenca.origem === 'facial' ? 'Reconhecimento facial' : 'Manual'}
                            </span>
                          </td>
                          <td><span className="text-muted">{presenca.camera_id || '-'}</span></td>
                          <td>
                            <span className={`badge ${statusBadge(presenca.status)}`}>
                              {presenca.status}
                            </span>
                          </td>
                          <td>
                            {typeof presenca.confianca === 'number'
                              ? `${Math.round(presenca.confianca * 100)}%`
                              : '-'}
                          </td>
                          <td><span className="badge bg-secondary">{presenca.recognition_event_id ? 'Criada' : '-'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
