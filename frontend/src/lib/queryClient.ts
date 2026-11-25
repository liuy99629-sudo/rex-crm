import { MutationCache, QueryClient } from '@tanstack/react-query'

/** How often the dashboard re-reads its numbers while it is open (ms). */
export const LIVE_REFETCH_MS = 10_000

/** Queries whose numbers depend on every contact, listing and deal. */
const SUMMARY_KEYS = [['dashboard'], ['pipeline']] as const

export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    // Any successful write (create, edit, delete, stage change) can move the dashboard numbers,
    // so mark them stale: open screens refetch now, others refetch when next shown.
    mutationCache: new MutationCache({
      onSuccess: () => Promise.all(SUMMARY_KEYS.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
    }),
    defaultOptions: {
      queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 },
    },
  })
  return queryClient
}
