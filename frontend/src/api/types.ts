export const DEAL_STAGES = [
  { value: 'lead', label: 'Lead' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'inspection', label: 'Inspection' },
  { value: 'offer', label: 'Offer' },
  { value: 'negotiation', label: 'Negotiation' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
] as const

export type DealStage = (typeof DEAL_STAGES)[number]['value']

export const CONTACT_TYPES = ['buyer', 'seller', 'investor', 'tenant', 'landlord'] as const
export type ContactType = (typeof CONTACT_TYPES)[number]

export const PROPERTY_TYPES = ['house', 'apartment', 'townhouse', 'land', 'commercial'] as const
export type PropertyType = (typeof PROPERTY_TYPES)[number]

export const PROPERTY_STATUSES = ['draft', 'active', 'under_offer', 'sold', 'withdrawn'] as const
export type PropertyStatus = (typeof PROPERTY_STATUSES)[number]

export const AU_STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'] as const

export interface User {
  id: number
  name: string
  email: string
  role: string
}

export interface NamedRef {
  id: number
  name: string
}

export interface Contact {
  id: number
  name: string
  email: string | null
  phone: string | null
  type: ContactType
  source: string | null
  budget_min: number | null
  budget_max: number | null
  notes: string | null
  agent?: NamedRef | null
  deals_count?: number
}

export interface ContactInput {
  name: string
  email: string | null
  phone: string | null
  type: ContactType
  source: string | null
  budget_min: number | null
  budget_max: number | null
  notes: string | null
}

export interface Property {
  id: number
  title: string
  address_line: string
  suburb: string
  state: string
  postcode: string
  type: PropertyType
  status: PropertyStatus
  price: number | null
  bedrooms: number | null
  bathrooms: number | null
  parking: number | null
  land_size_sqm: number | null
  description: string | null
  listed_at: string | null
  owner_id: number | null
  owner?: NamedRef | null
}

export type PropertyInput = Omit<Property, 'id' | 'owner'>

export interface DealActivity {
  id: number
  type: 'note' | 'stage_change'
  body: string | null
  user?: NamedRef | null
  created_at: string
}

export interface Deal {
  id: number
  title: string
  stage: DealStage
  stage_label: string
  value: number
  expected_close_date: string | null
  notes: string | null
  contact_id: number
  property_id: number | null
  contact?: NamedRef | null
  property?: { id: number; title: string; suburb: string } | null
  agent?: NamedRef | null
  activities?: DealActivity[]
}

export interface DealInput {
  title: string
  contact_id: number
  property_id: number | null
  value: number
  expected_close_date: string | null
  notes: string | null
}

export interface PipelineColumn {
  stage: DealStage
  label: string
  count: number
  total_value: number
  deals: Deal[]
}

export interface DashboardStats {
  contacts: number
  active_listings: number
  open_deals: number
  pipeline_value: number
  won_this_month: number
  won_value_this_month: number
}

export interface Paginated<T> {
  data: T[]
  meta: { current_page: number; last_page: number; per_page: number; total: number }
}
