import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type DragEvent, type FormEvent } from 'react'
import { contactsApi, dealsApi, pipelineApi, propertiesApi } from '../api'
import { ApiError } from '../api/client'
import { DEAL_STAGES, type Deal, type DealInput, type DealStage, type PipelineColumn } from '../api/types'
import Modal from '../components/Modal'
import { ErrorBox, Field, PageHeader } from '../components/ui'
import { formatCurrency, formatDate, formatDateTime, toNumberOrNull, toStringOrNull } from '../lib/format'
import { moveDeal } from '../lib/pipeline'

export default function PipelinePage() {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [openDealId, setOpenDealId] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState<DealStage | null>(null)

  const board = useQuery({ queryKey: ['pipeline'], queryFn: pipelineApi.board })

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['pipeline'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  // Dropping a card moves it instantly (optimistic), then the API saves it and queues the worker job.
  const move = useMutation({
    mutationFn: ({ id, stage }: { id: number; stage: DealStage }) => dealsApi.setStage(id, stage),
    onMutate: async ({ id, stage }) => {
      await queryClient.cancelQueries({ queryKey: ['pipeline'] })
      const previous = queryClient.getQueryData<PipelineColumn[]>(['pipeline'])
      if (previous) queryClient.setQueryData(['pipeline'], moveDeal(previous, id, stage))
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(['pipeline'], ctx.previous)
    },
    onSettled: refresh,
  })

  const onDrop = (e: DragEvent, stage: DealStage) => {
    e.preventDefault()
    setDragOver(null)
    const id = Number(e.dataTransfer.getData('text/plain'))
    if (id) move.mutate({ id, stage })
  }

  return (
    <>
      <PageHeader
        title="Sales pipeline"
        action={
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            New deal
          </button>
        }
      />
      <ErrorBox error={board.error ?? move.error} />
      {board.isLoading && <p className="muted">Loading...</p>}

      <div className="kanban">
        {board.data?.map((column) => (
          <section
            key={column.stage}
            className={dragOver === column.stage ? 'column drag-over' : 'column'}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(column.stage)
            }}
            onDragLeave={() => setDragOver((s) => (s === column.stage ? null : s))}
            onDrop={(e) => onDrop(e, column.stage)}
          >
            <header className={`column-header stage-${column.stage}`}>
              <span>{column.label}</span>
              <span className="column-count">{column.count}</span>
            </header>
            <div className="column-total">{formatCurrency(column.total_value)}</div>
            <div className="column-cards">
              {column.deals.map((deal) => (
                <article
                  key={deal.id}
                  className="deal-card"
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData('text/plain', String(deal.id))}
                  onClick={() => setOpenDealId(deal.id)}
                >
                  <div className="deal-title">{deal.title}</div>
                  <div className="muted small">{deal.contact?.name}</div>
                  {deal.property && (
                    <div className="muted small">
                      {deal.property.title}
                    </div>
                  )}
                  <div className="deal-value">{formatCurrency(deal.value)}</div>
                </article>
              ))}
              {column.deals.length === 0 && <div className="column-empty">Drop deals here</div>}
            </div>
          </section>
        ))}
      </div>

      {creating && (
        <DealForm
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            refresh()
          }}
        />
      )}
      {openDealId !== null && (
        <DealDetail dealId={openDealId} onClose={() => setOpenDealId(null)} onChanged={refresh} />
      )}
    </>
  )
}

function DealForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState('')
  const [contactId, setContactId] = useState('')
  const [propertyId, setPropertyId] = useState('')
  const [value, setValue] = useState('')
  const [closeDate, setCloseDate] = useState('')
  const [notes, setNotes] = useState('')

  const contacts = useQuery({ queryKey: ['contacts', 'options'], queryFn: () => contactsApi.list({ per_page: 100 }) })
  const properties = useQuery({ queryKey: ['properties', 'options'], queryFn: () => propertiesApi.list({ per_page: 100 }) })

  const save = useMutation({
    mutationFn: (body: DealInput) => dealsApi.create(body),
    onSuccess: onSaved,
  })
  const err = save.error instanceof ApiError ? save.error : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({
      title,
      contact_id: Number(contactId),
      property_id: toNumberOrNull(propertyId),
      value: toNumberOrNull(value) ?? 0,
      expected_close_date: toStringOrNull(closeDate),
      notes: toStringOrNull(notes),
    })
  }

  return (
    <Modal title="New deal" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label="Title" error={err?.field('title')}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus placeholder="Purchase - Smith family" />
        </Field>
        <Field label="Contact" error={err?.field('contact_id')}>
          <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
            <option value="">Select a contact</option>
            {contacts.data?.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Property (optional)" error={err?.field('property_id')}>
          <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
            <option value="">None</option>
            {properties.data?.data.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </Field>
        <div className="form-row">
          <Field label="Deal value (AUD)" error={err?.field('value')}>
            <input type="number" min={0} value={value} onChange={(e) => setValue(e.target.value)} />
          </Field>
          <Field label="Expected close" error={err?.field('expected_close_date')}>
            <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)} />
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
            {save.isPending ? 'Saving...' : 'Create deal'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function DealDetail({ dealId, onClose, onChanged }: { dealId: number; onClose: () => void; onChanged: () => void }) {
  const queryClient = useQueryClient()
  const [note, setNote] = useState('')

  const deal = useQuery({ queryKey: ['deal', dealId], queryFn: () => dealsApi.get(dealId) })

  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: ['deal', dealId] })
    onChanged()
  }

  const setStage = useMutation({
    mutationFn: (stage: DealStage) => dealsApi.setStage(dealId, stage),
    onSuccess: () => {
      reload()
      // The activity entry is written by the queue worker a moment later: check again shortly.
      setTimeout(() => void queryClient.invalidateQueries({ queryKey: ['deal', dealId] }), 1500)
    },
  })

  const addNote = useMutation({
    mutationFn: (body: string) => dealsApi.addNote(dealId, body),
    onSuccess: () => {
      setNote('')
      reload()
    },
  })

  const deleteNote = useMutation({
    mutationFn: (activityId: number) => dealsApi.deleteNote(dealId, activityId),
    onSuccess: reload,
  })

  const remove = useMutation({
    mutationFn: () => dealsApi.remove(dealId),
    onSuccess: () => {
      onChanged()
      onClose()
    },
  })

  const d: Deal | undefined = deal.data

  return (
    <Modal title={d?.title ?? 'Deal'} onClose={onClose} wide>
      <ErrorBox error={deal.error ?? setStage.error ?? addNote.error ?? deleteNote.error ?? remove.error} />
      {deal.isLoading && <p className="muted">Loading...</p>}
      {d && (
        <div className="deal-detail">
          <div className="deal-meta">
            <div>
              <span className="muted small">Contact</span>
              <div>{d.contact?.name ?? '-'}</div>
            </div>
            <div>
              <span className="muted small">Property</span>
              <div>{d.property ? `${d.property.title}, ${d.property.suburb}` : '-'}</div>
            </div>
            <div>
              <span className="muted small">Value</span>
              <div>{formatCurrency(d.value)}</div>
            </div>
            <div>
              <span className="muted small">Expected close</span>
              <div>{formatDate(d.expected_close_date)}</div>
            </div>
            <div>
              <span className="muted small">Agent</span>
              <div>{d.agent?.name ?? '-'}</div>
            </div>
            <div>
              <span className="muted small">Stage</span>
              <select value={d.stage} onChange={(e) => setStage.mutate(e.target.value as DealStage)} disabled={setStage.isPending}>
                {DEAL_STAGES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {d.notes && <p className="deal-notes">{d.notes}</p>}

          <h3>Activity</h3>
          <form
            className="note-form"
            onSubmit={(e) => {
              e.preventDefault()
              if (note.trim()) addNote.mutate(note.trim())
            }}
          >
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note..." />
            <button className="btn btn-primary" disabled={addNote.isPending || !note.trim()}>
              Add
            </button>
          </form>
          <ul className="timeline">
            {d.activities?.map((a) => (
              <li key={a.id} className={`timeline-item ${a.type}`}>
                <div>{a.body}</div>
                <div className="muted small">
                  {a.user?.name ?? 'System'} &middot; {formatDateTime(a.created_at)}
                  {a.type === 'note' && (
                    <>
                      {' '}
                      &middot;{' '}
                      <button
                        type="button"
                        className="link-danger"
                        onClick={() => window.confirm('Delete this note?') && deleteNote.mutate(a.id)}
                        disabled={deleteNote.isPending}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
            {d.activities?.length === 0 && <li className="muted">No activity yet.</li>}
          </ul>

          <div className="form-actions">
            <button
              className="btn btn-danger"
              onClick={() => window.confirm('Delete this deal?') && remove.mutate()}
              disabled={remove.isPending}
            >
              Delete deal
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
