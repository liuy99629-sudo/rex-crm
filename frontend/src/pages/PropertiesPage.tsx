import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { contactsApi, propertiesApi } from '../api'
import { ApiError } from '../api/client'
import {
  AU_STATES,
  PROPERTY_STATUSES,
  PROPERTY_TYPES,
  type Property,
  type PropertyInput,
  type PropertyStatus,
  type PropertyType,
} from '../api/types'
import Modal from '../components/Modal'
import { Badge, ErrorBox, Field, PageHeader, Pagination } from '../components/ui'
import { useConfirm } from '../components/useConfirm'
import { useDebounced } from '../components/useDebounced'
import { formatCurrency, humanize, toNumberOrNull, toStringOrNull } from '../lib/format'

export default function PropertiesPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Property | 'new' | null>(null)
  const q = useDebounced(search)
  const { confirm, dialog } = useConfirm()

  const list = useQuery({
    queryKey: ['properties', { q, status, type, page }],
    queryFn: () => propertiesApi.list({ q, status, type, page }),
    placeholderData: (prev) => prev,
  })

  const remove = useMutation({
    mutationFn: (id: number) => propertiesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['properties'] }),
  })

  const reset = () => setPage(1)

  return (
    <>
      <PageHeader
        title="Properties"
        action={
          <button className="btn btn-primary" onClick={() => setEditing('new')}>
            New listing
          </button>
        }
      />

      <div className="toolbar">
        <input
          placeholder="Search title, address or suburb"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            reset()
          }}
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value)
            reset()
          }}
        >
          <option value="">All statuses</option>
          {PROPERTY_STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value)
            reset()
          }}
        >
          <option value="">All types</option>
          {PROPERTY_TYPES.map((t) => (
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
              <th>Listing</th>
              <th>Status</th>
              <th>Type</th>
              <th>Price</th>
              <th>Bed / Bath / Car</th>
              <th>Vendor</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.data?.data.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.title}</strong>
                  <div className="muted small">
                    {p.address_line}, {p.suburb} {p.state} {p.postcode}
                  </div>
                </td>
                <td>
                  <Badge value={p.status} />
                </td>
                <td>{p.type}</td>
                <td>{formatCurrency(p.price)}</td>
                <td>
                  {p.bedrooms ?? '-'} / {p.bathrooms ?? '-'} / {p.parking ?? '-'}
                </td>
                <td>{p.owner?.name ?? '-'}</td>
                <td className="actions">
                  <button className="btn" onClick={() => setEditing(p)}>
                    Edit
                  </button>
                  <button className="btn btn-danger" onClick={() => confirm(`Delete ${p.title}?`, () => remove.mutate(p.id))}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {list.data?.data.length === 0 && (
              <tr>
                <td colSpan={7} className="empty">
                  No properties found.
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

      {editing && <PropertyForm property={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
      {dialog}
    </>
  )
}

function PropertyForm({ property, onClose }: { property: Property | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(property?.title ?? '')
  const [address, setAddress] = useState(property?.address_line ?? '')
  const [suburb, setSuburb] = useState(property?.suburb ?? '')
  const [state, setState] = useState(property?.state ?? 'NSW')
  const [postcode, setPostcode] = useState(property?.postcode ?? '')
  const [type, setType] = useState<PropertyType>(property?.type ?? 'house')
  const [status, setStatus] = useState<PropertyStatus>(property?.status ?? 'draft')
  const [price, setPrice] = useState(property?.price?.toString() ?? '')
  const [bedrooms, setBedrooms] = useState(property?.bedrooms?.toString() ?? '')
  const [bathrooms, setBathrooms] = useState(property?.bathrooms?.toString() ?? '')
  const [parking, setParking] = useState(property?.parking?.toString() ?? '')
  const [land, setLand] = useState(property?.land_size_sqm?.toString() ?? '')
  const [description, setDescription] = useState(property?.description ?? '')
  const [ownerId, setOwnerId] = useState(property?.owner_id?.toString() ?? '')

  const contacts = useQuery({
    queryKey: ['contacts', 'options'],
    queryFn: () => contactsApi.list({ per_page: 100 }),
  })

  const save = useMutation({
    mutationFn: (body: PropertyInput) => (property ? propertiesApi.update(property.id, body) : propertiesApi.create(body)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['properties'] })
      onClose()
    },
  })

  const err = save.error instanceof ApiError ? save.error : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({
      title,
      address_line: address,
      suburb,
      state,
      postcode,
      type,
      status,
      price: toNumberOrNull(price),
      bedrooms: toNumberOrNull(bedrooms),
      bathrooms: toNumberOrNull(bathrooms),
      parking: toNumberOrNull(parking),
      land_size_sqm: toNumberOrNull(land),
      description: toStringOrNull(description),
      listed_at: property?.listed_at ?? null,
      owner_id: toNumberOrNull(ownerId),
    })
  }

  return (
    <Modal title={property ? 'Edit listing' : 'New listing'} onClose={onClose} wide>
      <form className="form" onSubmit={submit}>
        <Field label="Title" error={err?.field('title')}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
        </Field>
        <Field label="Street address" error={err?.field('address_line')}>
          <input value={address} onChange={(e) => setAddress(e.target.value)} required />
        </Field>
        <div className="form-row form-row-3">
          <Field label="Suburb" error={err?.field('suburb')}>
            <input value={suburb} onChange={(e) => setSuburb(e.target.value)} required />
          </Field>
          <Field label="State" error={err?.field('state')}>
            <select value={state} onChange={(e) => setState(e.target.value)}>
              {AU_STATES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Postcode" error={err?.field('postcode')}>
            <input value={postcode} onChange={(e) => setPostcode(e.target.value)} maxLength={4} required />
          </Field>
        </div>
        <div className="form-row form-row-3">
          <Field label="Type" error={err?.field('type')}>
            <select value={type} onChange={(e) => setType(e.target.value as PropertyType)}>
              {PROPERTY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status" error={err?.field('status')}>
            <select value={status} onChange={(e) => setStatus(e.target.value as PropertyStatus)}>
              {PROPERTY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Price (AUD)" error={err?.field('price')}>
            <input type="number" min={0} value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
        </div>
        <div className="form-row form-row-4">
          <Field label="Bedrooms" error={err?.field('bedrooms')}>
            <input type="number" min={0} value={bedrooms} onChange={(e) => setBedrooms(e.target.value)} />
          </Field>
          <Field label="Bathrooms" error={err?.field('bathrooms')}>
            <input type="number" min={0} value={bathrooms} onChange={(e) => setBathrooms(e.target.value)} />
          </Field>
          <Field label="Parking" error={err?.field('parking')}>
            <input type="number" min={0} value={parking} onChange={(e) => setParking(e.target.value)} />
          </Field>
          <Field label="Land (sqm)" error={err?.field('land_size_sqm')}>
            <input type="number" min={0} value={land} onChange={(e) => setLand(e.target.value)} />
          </Field>
        </div>
        <Field label="Vendor (owner)" error={err?.field('owner_id')}>
          <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
            <option value="">None</option>
            {contacts.data?.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Description" error={err?.field('description')}>
          <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
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
