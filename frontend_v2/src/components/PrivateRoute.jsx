import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../services/AuthContext'

export default function PrivateRoute({ children }) {
  const { usuario, carregandoSessao } = useAuth()
  const location = useLocation()
  if (carregandoSessao) {
    return <div className="min-vh-100 d-flex align-items-center justify-content-center"><div className="spinner-border text-primary" role="status" /></div>
  }
  return usuario
    ? children
    : <Navigate to="/" state={{ from: location }} replace />
}
