import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { contactsApi } from '../api'
import { ApiError } from '../api/client'
import { CONTACT_TYPES, type Contact, type ContactInput, type ContactType } from '../api/types'
import Modal from '../components/Modal'
import { Badge, ErrorBox, Field, PageHeader, Pagination } from '../components/ui'
import { useDebounced } from '../components/useDebounced'
import { formatBudget, toNumberOrNull, toStringOrNull } from '../lib/format'

export default function ContactsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Contact | 'new' | null>(null)
  const q = useDebounced(search)

  const list = useQuery({
    queryKey: ['contacts', { q, type, page }],
    queryFn: () => contactsApi.list({ q, type, page }),
    placeholderData: (prev) => prev,
  })

  const remove = useMutation({
    mutationFn: (id: number) => contactsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contacts'] }),
  })

  return (
    <>
      <PageHeader
        title="Contacts"
        action={
          <button className="btn btn-primary" onClick={() => setEditing('new')}>
            New contact
          </button>
        }
      />

      <div className="toolbar">
        <input
          placeholder="Search name, email or phone"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value)
            setPage(1)
          }}
        >
          <option value="">All types</option>
          {CONTACT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <ErrorBox error={list.error ?? remove.error} />

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Budget</th>
              <th>Deals</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.data?.data.map((c) => (
              <tr key={c.id}>
                <td>
                  <strong>{c.name}</strong>
                  {c.agent && <div className="muted small">Agent: {c.agent.name}</div>}
                </td>
                <td>
                  <Badge value={c.type} />
                </td>
                <td>{c.email ?? '-'}</td>
                <td>{c.phone ?? '-'}</td>
                <td>
                  {formatBudget(c.budget_min, c.budget_max)}
                </td>
                <td>{c.deals_count ?? 0}</td>
                <td className="actions">
                  <button className="btn" onClick={() => setEditing(c)}>
                    Edit
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => window.confirm(`Delete ${c.name}? Their deals will be deleted too.`) && remove.mutate(c.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {list.data?.data.length === 0 && (
              <tr>
                <td colSpan={7} className="empty">
                  No contacts found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {list.isLoading && <p className="muted pad">Loading...</p>}
      </div>

      {list.data && (
        <Pagination page={list.data.meta.current_page} lastPage={list.data.meta.last_page} total={list.data.meta.total} onChange={setPage} />
      )}

      {editing && <ContactForm contact={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

function ContactForm({ contact, onClose }: { contact: Contact | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(contact?.name ?? '')
  const [email, setEmail] = useState(contact?.email ?? '')
  const [phone, setPhone] = useState(contact?.phone ?? '')
  const [type, setType] = useState<ContactType>(contact?.type ?? 'buyer')
  const [source, setSource] = useState(contact?.source ?? '')
  const [budgetMin, setBudgetMin] = useState(contact?.budget_min?.toString() ?? '')
  const [budgetMax, setBudgetMax] = useState(contact?.budget_max?.toString() ?? '')
  const [notes, setNotes] = useState(contact?.notes ?? '')

  const save = useMutation({
    mutationFn: (body: ContactInput) => (contact ? contactsApi.update(contact.id, body) : contactsApi.create(body)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['contacts'] })
      onClose()
    },
  })

  const err = save.error instanceof ApiError ? save.error : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({
      name,
      email: toStringOrNull(email),
      phone: toStringOrNull(phone),
      type,
      source: toStringOrNull(source),
      budget_min: toNumberOrNull(budgetMin),
      budget_max: toNumberOrNull(budgetMax),
      notes: toStringOrNull(notes),
    })
  }

  return (
    <Modal title={contact ? 'Edit contact' : 'New contact'} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label="Name" error={err?.field('name')}>
          <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        </Field>
        <div className="form-row">
          <Field label="Email" error={err?.field('email')}>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Phone" error={err?.field('phone')}>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Type" error={err?.field('type')}>
            <select value={type} onChange={(e) => setType(e.target.value as ContactType)}>
              {CONTACT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Lead source" error={err?.field('source')}>
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Domain, referral..." />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Budget min (AUD)" error={err?.field('budget_min')}>
            <input type="number" min={0} value={budgetMin} onChange={(e) => setBudgetMin(e.target.value)} />
          </Field>
          <Field label="Budget max (AUD)" error={err?.field('budget_max')}>
            <input type="number" min={0} value={budgetMax} onChange={(e) => setBudgetMax(e.target.value)} />
          </Field>
        </div>
        <Field label="Notes" error={err?.field('notes')}>
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        {err && !Object.keys(err.errors).length && <ErrorBox error={err} />}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={save.isPending}>
            {save.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
