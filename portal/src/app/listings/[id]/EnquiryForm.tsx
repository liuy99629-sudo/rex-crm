'use client'

import { useActionState } from 'react'
import { submitEnquiry, type EnquiryState } from './actions'

export function EnquiryForm({ listingId }: { listingId: string }) {
  const [state, action, pending] = useActionState<EnquiryState, FormData>(submitEnquiry, { status: 'idle' })

  if (state.status === 'sent') {
    return (
      <div className="sent" role="status">
        <p>
          <strong>{state.message}</strong>
        </p>
        <p className="muted">Reference {state.reference}</p>
      </div>
    )
  }

  const err = state.status === 'error' ? state.fields : {}

  return (
    <form action={action} className="enquiry-form" noValidate>
      <input type="hidden" name="listingId" value={listingId} />
      {/* Honeypot: hidden from people, filled in by bots. */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" className="hp" aria-hidden />
      <label>
        Name
        <input name="name" required maxLength={255} autoComplete="name" />
        {err.name && <span className="field-error">{err.name}</span>}
      </label>
      <label>
        Email
        <input name="email" type="email" required maxLength={255} autoComplete="email" />
        {err.email && <span className="field-error">{err.email}</span>}
      </label>
      <label>
        Phone (optional)
        <input name="phone" type="tel" maxLength={50} autoComplete="tel" />
      </label>
      <label>
        Message
        <textarea name="message" required maxLength={2000} rows={4} defaultValue="Hi, is this property still available? I'd like to arrange an inspection." />
        {err.message && <span className="field-error">{err.message}</span>}
      </label>
      {state.status === 'error' && <p className="form-error">{state.message}</p>}
      <button type="submit" disabled={pending}>
        {pending ? 'Sending…' : 'Send enquiry'}
      </button>
      <p className="muted small">Your details go only to the listing agent at Rex Realty.</p>
    </form>
  )
}
