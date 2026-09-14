import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useAlunos } from '../hooks/useAlunos'
import { useAuth } from '../services/AuthContext'
import { resolveMediaUrl } from '../services/api'

function Card({ titulo, valor, cor }) {
  return (
    <div className="card shadow-sm p-4" style={{ borderRadius: 12, border: 'none' }}>
      <div className="text-muted small text-uppercase mb-1" style={{ letterSpacing: '.05em', fontSize: 11 }}>{titulo}</div>
      <div className={`fs-1 fw-semibold ${cor}`}>{valor}</div>
    </div>
  )
}

export default function Dashboard() {
  const { usuario } = useAuth()
  const { alunos, carregando } = useAlunos()
  const ultimos = alunos.slice(0, 5)

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h4 className="mb-0 fw-semibold">Dashboard</h4>
          <span className="text-muted small">Bem-vindo, {usuario?.nome}</span>
        </div>

        <div className="row g-3 mb-4">
          <div className="col-md-4">
            <Card titulo="Total de alunos" valor={carregando ? '—' : alunos.length} cor="text-primary" />
          </div>
          <div className="col-md-4">
            <Card titulo="Últimos cadastrados" valor={carregando ? '—' : ultimos.length} cor="text-success" />
          </div>
          <div className="col-md-4">
            <Card titulo="Conta" valor={<span style={{ fontSize: 15 }}>{usuario?.email}</span>} cor="text-warning" />
          </div>
        </div>

        <div className="card shadow-sm p-4" style={{ borderRadius: 12, border: 'none' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h6 className="mb-0 fw-semibold">Últimos alunos cadastrados</h6>
            <Link to="/alunos" className="btn btn-sm btn-outline-primary">Ver todos</Link>
          </div>

          {carregando ? (
            <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-primary"></div></div>
          ) : ultimos.length === 0 ? (
            <p className="text-muted mb-0">
              Nenhum aluno ainda. <Link to="/alunos/novo">Cadastrar agora</Link>.
            </p>
          ) : (
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th style={{ width: 52 }}>Foto</th>
                  <th>Nome</th>
                  <th>Inscricao</th>
                  <th>Telefone</th>
                  <th style={{ width: 80 }}>Ação</th>
                </tr>
              </thead>
              <tbody>
                {ultimos.map(aluno => (
                  <tr key={aluno.id}>
                    <td>
                      {aluno.foto
                        ? <img src={resolveMediaUrl(aluno.foto)} width={40} height={40}
                            style={{ borderRadius: '50%', objectFit: 'cover' }} alt={aluno.nome} />
                        : <span style={{ fontSize: 28, color: '#d1d5db' }}><i className="fa fa-user-circle"></i></span>
                      }
                    </td>
                    <td className="fw-medium">{aluno.nome}</td>
                    <td className="text-muted">{aluno.numero_inscricao}</td>
                    <td className="text-muted">{aluno.telefone}</td>
                    <td>
                      <Link to={`/alunos/editar/${aluno.id}`} className="btn btn-sm btn-outline-primary">
                        <i className="fa fa-edit"></i>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}
