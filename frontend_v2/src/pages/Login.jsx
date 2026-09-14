import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../services/AuthContext'
import Toast from '../components/Toast'

export default function Login() {
  const { login, registrar } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const destino = location.state?.from?.pathname || '/alunos'

  const [aba, setAba] = useState('login')
  const [loginForm, setLoginForm] = useState({ email: '', senha: '' })
  const [regForm, setRegForm] = useState({ nome: '', email: '', senha: '' })
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [tentarNovoEm, setTentarNovoEm] = useState(null)

  async function handleLogin(e) {
    e.preventDefault()
    setErro('')
    setCarregando(true)
    try {
      await login(loginForm.email, loginForm.senha)
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
        setErro(err.response?.data?.detail || err.response?.data?.erro || 'Erro ao fazer login')
      }
    } finally {
      setCarregando(false)
    }
  }

  async function handleRegistrar(e) {
    e.preventDefault()
    setErro('')
    setSucesso('')
    setCarregando(true)
    try {
      await registrar(regForm.nome, regForm.email, regForm.senha)
      setSucesso('Conta criada! Faça login.')
      setAba('login')
      setRegForm({ nome: '', email: '', senha: '' })
    } catch (err) {
      // Tratamento específico para rate limit
      if (err.status === 429 || err.response?.status === 429) {
        const segundos = err.retryAfter || 60
        setTentarNovoEm(segundos)
        setErro(`⏱️ Muitas requisições. Tente novamente em ${segundos}s`)
        
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
        setErro(err.response?.data?.detail || err.response?.data?.erro || 'Erro ao criar conta')
      }
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center" style={{ background: '#f4f6f9' }}>
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-md-5">
            <div className="text-center mb-4">
              <i className="fa fa-school fa-3x text-primary mb-2 d-block"></i>
              <h4 className="fw-semibold">Sistema Escolar</h4>
            </div>

            <Toast mensagem={erro} tipo="danger" onClose={() => setErro('')} />
            <Toast mensagem={sucesso} tipo="success" onClose={() => setSucesso('')} />

            <div className="card shadow-sm" style={{ borderRadius: 14, border: 'none' }}>
              <div className="card-header bg-white border-0 pt-4 px-4">
                <ul className="nav nav-tabs card-header-tabs">
                  <li className="nav-item">
                    <button className={`nav-link ${aba === 'login' ? 'active' : ''}`}
                      onClick={() => { setAba('login'); setErro('') }}>
                      Entrar
                    </button>
                  </li>
                  <li className="nav-item">
                    <button className={`nav-link ${aba === 'registrar' ? 'active' : ''}`}
                      onClick={() => { setAba('registrar'); setErro('') }}>
                      Criar conta
                    </button>
                  </li>
                </ul>
              </div>

              <div className="card-body p-4">
                {aba === 'login' ? (
                  <form onSubmit={handleLogin}>
                    <div className="mb-3">
                      <label className="form-label">E-mail</label>
                      <input type="email" className="form-control" required autoFocus
                        value={loginForm.email}
                        onChange={e => setLoginForm({ ...loginForm, email: e.target.value })} />
                    </div>
                    <div className="mb-4">
                      <label className="form-label">Senha</label>
                      <input type="password" className="form-control" required
                        value={loginForm.senha}
                        onChange={e => setLoginForm({ ...loginForm, senha: e.target.value })} />
                    </div>
                    <button type="submit" className="btn btn-primary w-100" disabled={carregando || tentarNovoEm}>
                      {carregando 
                        ? <><span className="spinner-border spinner-border-sm me-2"></span>Entrando...</> 
                        : tentarNovoEm
                        ? <><i className="fa fa-hourglass-end me-2"></i>Aguarde {tentarNovoEm}s</>
                        : 'Entrar'
                      }
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleRegistrar}>
                    <div className="mb-3">
                      <label className="form-label">Nome</label>
                      <input type="text" className="form-control" required autoFocus
                        value={regForm.nome}
                        onChange={e => setRegForm({ ...regForm, nome: e.target.value })} />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">E-mail</label>
                      <input type="email" className="form-control" required
                        value={regForm.email}
                        onChange={e => setRegForm({ ...regForm, email: e.target.value })} />
                    </div>
                    <div className="mb-4">
                      <label className="form-label">Senha <small className="text-muted">(mín. 6 caracteres)</small></label>
                      <input type="password" className="form-control" required minLength={6}
                        value={regForm.senha}
                        onChange={e => setRegForm({ ...regForm, senha: e.target.value })} />
                    </div>
                    <button type="submit" className="btn btn-success w-100" disabled={carregando || tentarNovoEm}>
                      {carregando 
                        ? <><span className="spinner-border spinner-border-sm me-2"></span>Criando...</> 
                        : tentarNovoEm
                        ? <><i className="fa fa-hourglass-end me-2"></i>Aguarde {tentarNovoEm}s</>
                        : 'Criar conta'
                      }
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
