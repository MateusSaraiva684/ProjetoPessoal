export default function Toast({ mensagem, tipo = 'danger', onClose }) {
  if (!mensagem) return null
  const cores = { danger: 'alert-danger', success: 'alert-success', warning: 'alert-warning' }
  return (
    <div className={`alert ${cores[tipo]} alert-dismissible`} role="alert">
      {mensagem}
      <button type="button" className="btn-close" onClick={onClose}></button>
    </div>
  )
}
