import { api } from './client'
import type {
  Contact,
  ContactInput,
  DashboardStats,
  Deal,
  DealActivity,
  DealInput,
  DealStage,
  Paginated,
  PipelineColumn,
  Property,
  PropertyInput,
  User,
} from './types'

type Query = Record<string, string | number | null | undefined>

export const authApi = {
  login: (email: string, password: string) =>
    api<{ token: string; user: User }>('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => api<User>('/auth/me'),
  logout: () => api<{ message: string }>('/auth/logout', { method: 'POST' }),
}

export const dashboardApi = {
  stats: () => api<{ data: DashboardStats }>('/dashboard').then((r) => r.data),
}

export const contactsApi = {
  list: (query: Query) => api<Paginated<Contact>>('/contacts', { query }),
  create: (body: ContactInput) => api<Contact>('/contacts', { method: 'POST', body }),
  update: (id: number, body: ContactInput) => api<Contact>(`/contacts/${id}`, { method: 'PUT', body }),
  remove: (id: number) => api<void>(`/contacts/${id}`, { method: 'DELETE' }),
}

export const propertiesApi = {
  list: (query: Query) => api<Paginated<Property>>('/properties', { query }),
  create: (body: PropertyInput) => api<Property>('/properties', { method: 'POST', body }),
  update: (id: number, body: PropertyInput) => api<Property>(`/properties/${id}`, { method: 'PUT', body }),
  remove: (id: number) => api<void>(`/properties/${id}`, { method: 'DELETE' }),
}

export const dealsApi = {
  get: (id: number) => api<Deal>(`/deals/${id}`),
  create: (body: DealInput) => api<Deal>('/deals', { method: 'POST', body }),
  update: (id: number, body: Partial<DealInput>) => api<Deal>(`/deals/${id}`, { method: 'PUT', body }),
  remove: (id: number) => api<void>(`/deals/${id}`, { method: 'DELETE' }),
  setStage: (id: number, stage: DealStage) => api<Deal>(`/deals/${id}/stage`, { method: 'PATCH', body: { stage } }),
  addNote: (id: number, body: string) => api<DealActivity>(`/deals/${id}/notes`, { method: 'POST', body: { body } }),
}

export const pipelineApi = {
  board: () => api<{ data: PipelineColumn[] }>('/pipeline').then((r) => r.data),
}
