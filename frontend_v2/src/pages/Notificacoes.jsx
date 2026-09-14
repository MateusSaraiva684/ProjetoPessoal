import { useEffect, useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
import Toast from '../components/Toast'
import api from '../services/api'

function formatarData(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function Notificacoes() {
  const [notificacoes, setNotificacoes] = useState([])
  const [status, setStatus] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [pagina, setPagina] = useState(1)
  const [temMais, setTemMais] = useState(false)

  const contadores = useMemo(() => ({
    pending: notificacoes.filter(n => n.status === 'pending').length,
    sent: notificacoes.filter(n => n.status === 'sent').length,
    failed: notificacoes.filter(n => n.status === 'failed').length,
  }), [notificacoes])

  async function carregar() {
    setCarregando(true)
    setErro('')
    try {
      const params = { page: pagina, limit: 25 }
      if (status) params.status = status
      const { data } = await api.get('/api/notificacoes', { params })
      setNotificacoes(data || [])
      setTemMais((data || []).length === 25)
    } catch (err) {
      setErro(err.response?.data?.erro || 'Nao foi possivel carregar notificacoes.')
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => { setPagina(1) }, [status])
  useEffect(() => { carregar() }, [status, pagina])

  async function reenviar(id) {
    setErro('')
    setSucesso('')
    try {
      await api.post(`/api/notificacoes/${id}/retry`)
      setSucesso('Reenvio solicitado.')
      await carregar()
    } catch (err) {
      setErro(err.response?.data?.erro || 'Nao foi possivel reenviar.')
    }
  }

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <div>
            <h4 className="mb-1 fw-semibold">Notificacoes</h4>
            <span className="text-muted small">Pendentes, enviadas e falhas do outbox</span>
          </div>
          <button className="btn btn-outline-primary" onClick={carregar} disabled={carregando}>
            <i className="fa fa-rotate me-1"></i>Atualizar
          </button>
        </div>

        <Toast mensagem={erro} tipo="danger" onClose={() => setErro('')} />
        <Toast mensagem={sucesso} tipo="success" onClose={() => setSucesso('')} />

        <div className="card shadow-sm p-3 mb-3" style={{ borderRadius: 12, border: 'none' }}>
          <div className="d-flex gap-2 align-items-center flex-wrap">
            <select className="form-select w-auto" value={status} onChange={e => setStatus(e.target.value)}>
              <option value="">Todos</option>
              <option value="pending">Pendentes</option>
              <option value="sent">Enviadas</option>
              <option value="failed">Falhas</option>
            </select>
            <span className="badge bg-warning text-dark">Pendentes {contadores.pending}</span>
            <span className="badge bg-success">Enviadas {contadores.sent}</span>
            <span className="badge bg-danger">Falhas {contadores.failed}</span>
          </div>
        </div>

        <div className="card shadow-sm" style={{ borderRadius: 12, border: 'none', overflow: 'hidden' }}>
          {carregando ? (
            <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>
          ) : notificacoes.length === 0 ? (
            <div className="text-center text-muted py-5">Nenhuma notificacao encontrada.</div>
          ) : (
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Status</th>
                    <th>Canal</th>
                    <th>Destino</th>
                    <th>Mensagem</th>
                    <th>Tentativas</th>
                    <th>Criada em</th>
                    <th>Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {notificacoes.map(n => (
                    <tr key={n.id}>
                      <td><span className="badge bg-secondary">{n.status}</span></td>
                      <td>{n.canal}</td>
                      <td>{n.telefone_destino}</td>
                      <td className="small">{n.mensagem}</td>
                      <td>{n.attempts}</td>
                      <td>{formatarData(n.created_at)}</td>
                      <td>
                        {n.status === 'failed' && (
                          <button className="btn btn-sm btn-outline-primary" onClick={() => reenviar(n.id)}>
                            <i className="fa fa-rotate me-1"></i>Reenviar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="d-flex justify-content-between align-items-center p-3 border-top">
                <small className="text-muted">Página {pagina}</small>
                <div className="btn-group">
                  <button className="btn btn-sm btn-outline-secondary" disabled={pagina <= 1 || carregando} onClick={() => setPagina(p => p - 1)}>Anterior</button>
                  <button className="btn btn-sm btn-outline-secondary" disabled={!temMais || carregando} onClick={() => setPagina(p => p + 1)}>Próxima</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
