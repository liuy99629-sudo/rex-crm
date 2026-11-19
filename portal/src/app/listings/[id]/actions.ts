'use server'

import { headers } from 'next/headers'
import { GatewayError, gql } from '@/lib/gateway'
import { ENQUIRY_MUTATION } from '@/lib/listings'

export type EnquiryState =
  | { status: 'idle' }
  | { status: 'sent'; reference: string; message: string }
  | { status: 'error'; message: string; fields: Record<string, string> }

const field = (form: FormData, name: string) => String(form.get(name) ?? '').trim()

/** Server Action: runs on the portal server, so the gateway URL never reaches the browser. */
export async function submitEnquiry(_: EnquiryState, form: FormData): Promise<EnquiryState> {
  const h = await headers()
  // The visitor's IP, so the CRM rate-limits per visitor (X-Forwarded-For from a proxy in front, if any).
  const clientIp = h.get('x-forwarded-for')?.split(',')[0].trim() || h.get('x-real-ip') || null

  try {
    const { submitEnquiry: res } = await gql<{ submitEnquiry: { reference: string; message: string } }>(
      ENQUIRY_MUTATION,
      {
        input: {
          listingId: field(form, 'listingId'),
          name: field(form, 'name'),
          email: field(form, 'email'),
          phone: field(form, 'phone') || null,
          message: field(form, 'message'),
          website: field(form, 'website') || null,
        },
      },
      { clientIp, revalidate: false },
    )
    return { status: 'sent', reference: res.reference, message: res.message }
  } catch (err) {
    if (err instanceof GatewayError) {
      const fields = Object.fromEntries(Object.entries(err.fields).map(([k, v]) => [k, v[0] ?? 'Invalid']))
      const message =
        err.code === 'BAD_USER_INPUT' ? 'Please check the highlighted fields.' : err.code ? err.message : 'Something went wrong. Please try again.'
      return { status: 'error', message, fields }
    }
    return { status: 'error', message: 'Something went wrong. Please try again.', fields: {} }
  }
}
