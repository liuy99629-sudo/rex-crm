import { MutationObserver } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { createQueryClient } from './queryClient'

describe('createQueryClient', () => {
  it('marks dashboard and pipeline data stale after any successful write', async () => {
    const client = createQueryClient()
    client.setQueryData(['dashboard'], { contacts: 16 })
    client.setQueryData(['pipeline'], [])
    client.setQueryData(['contacts'], [])

    await new MutationObserver(client, { mutationFn: async () => null }).mutate()

    expect(client.getQueryState(['dashboard'])?.isInvalidated).toBe(true)
    expect(client.getQueryState(['pipeline'])?.isInvalidated).toBe(true)
    expect(client.getQueryState(['contacts'])?.isInvalidated).toBe(false)
  })

  it('leaves the dashboard alone when a write fails', async () => {
    const client = createQueryClient()
    client.setQueryData(['dashboard'], { contacts: 16 })

    const failing = new MutationObserver(client, {
      mutationFn: async () => {
        throw new Error('422')
      },
    })
    await expect(failing.mutate()).rejects.toThrow('422')

    expect(client.getQueryState(['dashboard'])?.isInvalidated).toBe(false)
  })
})
