import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../services/AuthContext'

export default function AdminRoute({ children }) {
  const { usuario, carregandoSessao } = useAuth()
  const location = useLocation()

  if (carregandoSessao) {
    return <div className="min-vh-100 d-flex align-items-center justify-content-center"><div className="spinner-border text-warning" role="status" /></div>
  }
  if (!usuario) return <Navigate to="/admin/login" state={{ from: location }} replace />
  if (!usuario.is_superuser) return <Navigate to="/alunos" replace />
  return children
}
