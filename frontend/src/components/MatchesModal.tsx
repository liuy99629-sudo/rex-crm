import { useQuery } from '@tanstack/react-query'
import type { MatchResult } from '../api/types'
import { matchTier } from '../lib/assistant'
import Modal from './Modal'
import { ErrorBox } from './ui'

/** Ranked buyer ↔ listing matches with the reasons behind each score. */
export default function MatchesModal({
  title,
  queryKey,
  load,
  describe,
  onClose,
}: {
  title: string
  queryKey: unknown[]
  load: () => Promise<MatchResult>
  describe: (detail: Record<string, string | number | null>) => string
  onClose: () => void
}) {
  const result = useQuery({ queryKey, queryFn: load, retry: false })

  return (
    <Modal title={title} onClose={onClose} wide>
      <ErrorBox error={result.error} />
      {result.isLoading && <p className="muted">Finding matches...</p>}
      {result.data && result.data.matches.length === 0 && <p className="muted">No suitable matches right now.</p>}
      <ol className="matches">
        {result.data?.matches.map((m) => (
          <li key={m.id} className="match">
            <div className="match-head">
              <strong>{m.name}</strong>
              <span className={`match-score ${matchTier(m.score)}`}>{Math.round(m.score)}</span>
            </div>
            <div className="muted small">{describe(m.detail)}</div>
            <ul className="match-reasons">
              {m.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      <p className="muted small">
        Score out of 100: budget fit plus how closely their notes match the listing description (local embeddings).
      </p>
    </Modal>
  )
}
