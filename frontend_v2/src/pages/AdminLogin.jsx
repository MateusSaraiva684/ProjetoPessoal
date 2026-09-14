import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../services/AuthContext'

export default function AdminLogin() {
  const navigate = useNavigate()
  const location = useLocation()
  const { usuario, login, logout } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [tentarNovoEm, setTentarNovoEm] = useState(null)

  if (usuario?.is_superuser) return <Navigate to="/admin" replace />
  if (usuario) return <Navigate to="/alunos" replace />

  async function handleLogin(e) {
    e.preventDefault()
    setErro('')
    setCarregando(true)

    try {
      const data = await login(email, senha)

      if (!data.usuario?.is_superuser) {
        await logout()
        setErro('Acesso restrito a administradores')
        return
      }

      const destino = location.state?.from?.pathname || '/admin'
      navigate(destino, { replace: true })
    } catch (err) {
      // Tratamento específico para rate limit
      if (err.status === 429 || err.response?.status === 429) {
        const segundos = err.retryAfter || 60
        setTentarNovoEm(segundos)
        setErro(`⏱️ Muitas tentativas. Tente novamente em ${segundos}s`)
        
        // Countdown do rate limit
        const interval = setInterval(() => {
          setTentarNovoEm(prev => {
            if (prev <= 1) {
              clearInterval(interval)
              setErro('')
              return null
            }
            return prev - 1
          })
        }, 1000)
      } else {
        setErro(err.response?.data?.erro || 'Credenciais inválidas')
      }
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center" style={{ background: '#111827' }}>
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-md-4">
            <div className="text-center mb-4">
              <i className="fa fa-shield-alt fa-3x text-warning mb-2 d-block"></i>
              <h4 className="text-white fw-semibold">Painel Administrativo</h4>
              <p className="text-secondary small">Entre com uma conta de administrador</p>
            </div>

            {erro && <div className="alert alert-danger">{erro}</div>}

            <div className="card p-4" style={{ borderRadius: 14, border: 'none', background: '#1f2937' }}>
              <form onSubmit={handleLogin}>
                <div className="mb-3">
                  <label className="form-label text-secondary small">E-mail admin</label>
                  <input
                    type="email"
                    className="form-control bg-dark text-white border-secondary"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div className="mb-4">
                  <label className="form-label text-secondary small">Senha</label>
                  <input
                    type="password"
                    className="form-control bg-dark text-white border-secondary"
                    value={senha}
                    onChange={e => setSenha(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn btn-warning w-100 fw-semibold" disabled={carregando || tentarNovoEm}>
                  {carregando
                    ? <><span className="spinner-border spinner-border-sm me-2"></span>Entrando...</>
                    : tentarNovoEm
                    ? <><i className="fa fa-hourglass-end me-2"></i>Aguarde {tentarNovoEm}s</>
                    : <><i className="fa fa-lock me-2"></i>Entrar</>}
                </button>
              </form>
            </div>

            <div className="text-center mt-3">
              <a href="/" className="text-secondary small">Voltar ao login principal</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
