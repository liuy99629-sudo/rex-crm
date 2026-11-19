import { useCallback, useState, type ReactNode } from 'react'
import Modal from './Modal'

interface Pending {
  message: string
  onConfirm: () => void
}

/**
 * In-page replacement for window.confirm. Embedded browsers (such as an app's preview pane)
 * may suppress native dialogs, which makes window.confirm return false without asking.
 * Render `dialog` somewhere in the component, then call `confirm(message, onConfirm)`.
 */
export function useConfirm(): { confirm: (message: string, onConfirm: () => void) => void; dialog: ReactNode } {
  const [pending, setPending] = useState<Pending | null>(null)
  const close = useCallback(() => setPending(null), [])
  const confirm = useCallback((message: string, onConfirm: () => void) => setPending({ message, onConfirm }), [])

  const dialog = pending && (
    <Modal title="Please confirm" onClose={close}>
      <p>{pending.message}</p>
      <div className="form-actions">
        <button type="button" className="btn" onClick={close} autoFocus>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => {
            pending.onConfirm()
            close()
          }}
        >
          Delete
        </button>
      </div>
    </Modal>
  )

  return { confirm, dialog }
}
