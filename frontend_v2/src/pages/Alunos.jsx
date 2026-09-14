import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Toast from '../components/Toast'
import { useAlunos } from '../hooks/useAlunos'
import { useAuth } from '../services/AuthContext'
import { resolveMediaUrl } from '../services/api'
import api from '../services/api'
import {
  getExternalIdReconhecimento,
  getSchoolIdReconhecimento,
  getStatusReconhecimentoAluno,
} from '../services/reconhecimento'

export default function Alunos() {
  const { usuario } = useAuth()
  const [turmaSelecionada, setTurmaSelecionada] = useState('')
  const [busca, setBusca] = useState('')
  const [biometriaStatus, setBiometriaStatus] = useState('')
  const [semFoto, setSemFoto] = useState(false)
  const [comErroBiometria, setComErroBiometria] = useState(false)
  const [turmas, setTurmas] = useState([])
  const [erroAcao, setErroAcao] = useState('')
  const [sucessoAcao, setSucessoAcao] = useState('')
  const [pagina, setPagina] = useState(1)

  const { alunos, paginacao, carregando, erro, deletar, recarregar } = useAlunos({
    turma: turmaSelecionada,
    busca,
    biometriaStatus,
    semFoto,
    comErroBiometria,
    pagina,
  })

  useEffect(() => { setPagina(1) }, [turmaSelecionada, busca, biometriaStatus, semFoto, comErroBiometria])

  // Carrega lista de turmas disponíveis (apenas uma vez)
  useEffect(() => {
    api.get('/api/alunos/turmas')
      .then(({ data }) => setTurmas(data))
      .catch(() => {})
  }, [])

  async function handleDeletar(id, nome) {
    if (!confirm(`Remover ${nome}?`)) return
    try {
      await deletar(id)
    } catch {
      setErroAcao('Erro ao remover aluno. Tente novamente.')
    }
  }

  function limparFiltros() {
    setTurmaSelecionada('')
    setBusca('')
    setBiometriaStatus('')
    setSemFoto(false)
    setComErroBiometria(false)
  }

  async function handleRetryBiometria(aluno) {
    setErroAcao('')
    setSucessoAcao('')
    try {
      await api.post(`/api/alunos/${aluno.id}/retry-biometria`)
      setSucessoAcao('Biometria reenviada.')
      await recarregar()
    } catch (err) {
      setErroAcao(err.response?.data?.erro || 'Nao foi possivel reenviar a biometria.')
    }
  }

  const temFiltro = turmaSelecionada || busca || biometriaStatus || semFoto || comErroBiometria
  const contadores = {
    total: paginacao?.total ?? alunos.length,
    ready: alunos.filter(a => a.biometria_status === 'ready').length,
    erro: alunos.filter(a => a.biometria_error || ['failed', 'needs_new_photo'].includes(a.biometria_status)).length,
    semFoto: alunos.filter(a => !a.foto).length,
  }

  return (
    <>
      <Navbar />
      <div className="container mt-4">

        {/* Cabeçalho */}
        <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
          <h4 className="mb-0 fw-semibold">
            Alunos{' '}
            <span className="badge bg-secondary fw-normal">{contadores.total}</span>
            {turmaSelecionada && (
              <span className="badge bg-primary fw-normal ms-2">{turmaSelecionada}</span>
            )}
          </h4>
          <Link to="/alunos/novo" className="btn btn-primary">
            <i className="fa fa-plus me-1"></i>Novo aluno
          </Link>
        </div>

        {/* Filtros */}
        <div className="card shadow-sm p-3 mb-4" style={{ borderRadius: 12, border: 'none' }}>
          <div className="row g-2 align-items-end">

            {/* Busca por nome ou inscrição */}
            <div className="col-md-5">
              <label className="form-label small text-muted mb-1">Buscar</label>
              <div className="input-group">
                <span className="input-group-text bg-light border-end-0">
                  <i className="fa fa-search text-muted"></i>
                </span>
                <input
                  type="text"
                  className="form-control border-start-0"
                  placeholder="Nome ou número de inscrição..."
                  value={busca}
                  onChange={e => setBusca(e.target.value)}
                />
              </div>
            </div>

            {/* Filtro por turma */}
            <div className="col-md-3">
              <label className="form-label small text-muted mb-1">Turma</label>
              <select
                className="form-select"
                value={turmaSelecionada}
                onChange={e => setTurmaSelecionada(e.target.value)}
              >
                <option value="">Todas as turmas</option>
                {turmas.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            <div className="col-md-2">
              <label className="form-label small text-muted mb-1">Biometria</label>
              <select
                className="form-select"
                value={biometriaStatus}
                onChange={e => setBiometriaStatus(e.target.value)}
              >
                <option value="">Todos</option>
                <option value="ready">Pronta</option>
                <option value="pending">Pendente</option>
                <option value="syncing">Sincronizando</option>
                <option value="failed">Falhou</option>
                <option value="needs_new_photo">Nova foto</option>
                <option value="no_photo">Sem foto</option>
              </select>
            </div>

            <div className="col-md-2">
              <label className="form-label small text-muted mb-1">Marcadores</label>
              <div className="d-flex flex-column small">
                <label><input type="checkbox" className="form-check-input me-1" checked={semFoto} onChange={e => setSemFoto(e.target.checked)} />Sem foto</label>
                <label><input type="checkbox" className="form-check-input me-1" checked={comErroBiometria} onChange={e => setComErroBiometria(e.target.checked)} />Com erro</label>
              </div>
            </div>

            {/* Limpar filtros */}
            <div className="col-md-2">
              <button
                className="btn btn-outline-secondary w-100"
                onClick={limparFiltros}
                disabled={!temFiltro}
              >
                <i className="fa fa-times me-1"></i>Limpar filtros
              </button>
            </div>
          </div>
          <div className="d-flex gap-2 flex-wrap mt-3 small">
            <span className="badge bg-secondary">Total {contadores.total}</span>
            <span className="badge bg-success">Prontas {contadores.ready}</span>
            <span className="badge bg-danger">Com erro {contadores.erro}</span>
            <span className="badge bg-warning text-dark">Sem foto {contadores.semFoto}</span>
          </div>
        </div>

        <Toast mensagem={erro} tipo="danger" onClose={() => {}} />
        <Toast mensagem={erroAcao} tipo="danger" onClose={() => setErroAcao('')} />
        <Toast mensagem={sucessoAcao} tipo="success" onClose={() => setSucessoAcao('')} />

        {carregando ? (
          <div className="text-center py-5">
            <div className="spinner-border text-primary"></div>
            <p className="text-muted mt-2">Carregando...</p>
          </div>
        ) : alunos.length === 0 && !erro ? (
          <div className="text-center py-5">
            <i className="fa fa-user-graduate fa-4x text-muted mb-3 d-block"></i>
            {temFiltro ? (
              <>
                <h5 className="text-muted">Nenhum aluno encontrado com esses filtros</h5>
                <button onClick={limparFiltros} className="btn btn-outline-secondary mt-3">
                  <i className="fa fa-times me-1"></i>Limpar filtros
                </button>
              </>
            ) : (
              <>
                <h5 className="text-muted">Nenhum aluno cadastrado ainda</h5>
                <Link to="/alunos/novo" className="btn btn-primary mt-3">
                  <i className="fa fa-plus me-1"></i>Cadastrar primeiro aluno
                </Link>
              </>
            )}
          </div>
        ) : (
          <div className="row g-3">
            {alunos.map(aluno => (
              <div key={aluno.id} className="col-xl-3 col-md-4 col-sm-6">
                <div className="card shadow-sm h-100" style={{ borderRadius: 12, border: 'none' }}>
                  {aluno.foto ? (
                    <img src={resolveMediaUrl(aluno.foto)} className="card-img-top"
                      style={{ height: 180, objectFit: 'cover', borderRadius: '12px 12px 0 0' }}
                      alt={aluno.nome} />
                  ) : (
                    <div style={{
                      height: 180, background: '#f3f4f6', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      borderRadius: '12px 12px 0 0', fontSize: 56, color: '#d1d5db'
                    }}>
                      <i className="fa fa-user"></i>
                    </div>
                  )}
                  <div className="card-body">
                    {(() => {
                      const statusReconhecimento = getStatusReconhecimentoAluno(aluno, usuario)
                      const schoolId = getSchoolIdReconhecimento(aluno, usuario)
                      return (
                        <div className="d-flex justify-content-between align-items-start gap-2 mb-2 flex-wrap">
                          <span className={`badge ${statusReconhecimento.badge}`} title={statusReconhecimento.detail}>
                            {statusReconhecimento.label}
                          </span>
                          <span className="badge bg-light text-dark border text-break" title="school_id usado pelo recognition-service">
                            {schoolId || 'sem school_id'}
                          </span>
                        </div>
                      )
                    })()}
                    <h6 className="card-title fw-semibold mb-1">{aluno.nome}</h6>
                    <p className="small text-primary fw-semibold mb-1">
                      Inscrição: {aluno.numero_inscricao}
                    </p>
                    {aluno.turma && (
                      <p className="mb-1">
                        <span className="badge bg-light text-dark border" style={{ fontSize: 11 }}>
                          <i className="fa fa-layer-group me-1 text-muted"></i>{aluno.turma}
                        </span>
                      </p>
                    )}
                    <p className="text-muted small mb-3">
                      <i className="fa fa-phone me-1"></i>{aluno.telefone}
                    </p>
                    {getExternalIdReconhecimento(aluno) && (
                      <p className="text-muted small mb-3 text-break">
                        <i className="fa fa-fingerprint me-1"></i>{getExternalIdReconhecimento(aluno)}
                      </p>
                    )}
                    <div className="d-flex gap-2 flex-wrap">
                      <Link to={`/presencas?aluno=${aluno.id}`}
                        className="btn btn-success btn-sm flex-fill">
                        <i className="fa fa-clipboard-check me-1"></i>Presenca
                      </Link>
                      <Link to={`/alunos/editar/${aluno.id}`}
                        className="btn btn-warning btn-sm flex-fill">
                        <i className="fa fa-edit me-1"></i>Editar
                      </Link>
                      <button onClick={() => handleDeletar(aluno.id, aluno.nome)}
                        className="btn btn-danger btn-sm flex-fill">
                        <i className="fa fa-trash me-1"></i>Remover
                      </button>
                      {['failed', 'pending', 'needs_new_photo', 'no_photo'].includes(aluno.biometria_status) && (
                        <button
                          type="button"
                          className="btn btn-outline-primary btn-sm w-100"
                          disabled={aluno.biometria_status === 'no_photo'}
                          onClick={() => handleRetryBiometria(aluno)}
                          title={aluno.biometria_status === 'no_photo' ? 'Cadastre uma foto antes de reenviar.' : 'Reenviar biometria para o recognition-service.'}
                        >
                          <i className="fa fa-rotate me-1"></i>Reenviar biometria
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {paginacao?.paginas_totais > 1 && (
          <div className="d-flex justify-content-between align-items-center mt-4">
            <small className="text-muted">
              Página {paginacao.pagina} de {paginacao.paginas_totais}
            </small>
            <div className="btn-group" role="group" aria-label="Paginação de alunos">
              <button className="btn btn-outline-secondary btn-sm" disabled={!paginacao.pagina || paginacao.pagina <= 1} onClick={() => setPagina(p => p - 1)}>
                Anterior
              </button>
              <button className="btn btn-outline-secondary btn-sm" disabled={!paginacao.proxima_pagina} onClick={() => setPagina(p => p + 1)}>
                Próxima
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
