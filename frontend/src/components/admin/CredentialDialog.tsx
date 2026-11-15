import { useState } from 'react'
import { Copy } from 'lucide-react'
import { Modal } from './Modal'
import type { CredentialResult } from '../../types/admin'

export function CredentialDialog({ result, onClose }: { result: CredentialResult; onClose: () => void }) {
  const [message, setMessage] = useState('')
  const [error, setError] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(result.credential)
      setError(false); setMessage('Đã sao chép.')
    } catch { setError(true); setMessage('Không thể sao chép. Hãy sao chép thủ công.') }
  }
  return <Modal title="Device credential" onClose={onClose}>
    <p className="mb-2 font-medium">{result.robot.name}</p>
    <p className="mb-4 text-sm text-amber-800">Chỉ hiển thị một lần. Hãy lưu trước khi đóng.</p>
    <label className="field-label" htmlFor="device-secret">Credential mới</label>
    <input className="field-input font-mono text-sm" id="device-secret" value={result.credential} readOnly autoComplete="off" spellCheck={false} onFocus={(event) => event.target.select()} />
    {message && <p className={error ? 'form-error mt-3' : 'mt-3 text-sm text-green-700'} role={error ? 'alert' : 'status'}>{message}</p>}
    <div className="modal-actions"><button className="secondary-button" onClick={() => { void copy() }}><Copy size={17} aria-hidden="true" />Sao chép</button><button className="primary-button" onClick={onClose}>Đã lưu</button></div>
  </Modal>
}
