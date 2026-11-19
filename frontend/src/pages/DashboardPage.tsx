import { useQuery } from '@tanstack/react-query'
import { dashboardApi, pipelineApi } from '../api'
import { ErrorBox, PageHeader } from '../components/ui'
import { formatCurrency } from '../lib/format'
import { LIVE_REFETCH_MS } from '../lib/queryClient'

// Keep the numbers current while the dashboard is open: poll, and catch up when the tab regains focus
// (e.g. after a teammate's change, or a queued job such as marking a property sold).
const live = { refetchInterval: LIVE_REFETCH_MS, refetchOnWindowFocus: true } as const

export default function DashboardPage() {
  const stats = useQuery({ queryKey: ['dashboard'], queryFn: dashboardApi.stats, ...live })
  const board = useQuery({ queryKey: ['pipeline'], queryFn: pipelineApi.board, ...live })

  const s = stats.data
  const maxCount = Math.max(1, ...(board.data?.map((c) => c.count) ?? [1]))

  return (
    <>
      <PageHeader
        title="Dashboard"
        action={
          stats.dataUpdatedAt > 0 && (
            <span className="muted small">
              Live &middot; updated {new Date(stats.dataUpdatedAt).toLocaleTimeString('en-AU')}
            </span>
          )
        }
      />
      <ErrorBox error={stats.error ?? board.error} />

      <div className="stat-grid">
        <Stat label="Contacts" value={s ? String(s.contacts) : '-'} />
        <Stat label="Active listings" value={s ? String(s.active_listings) : '-'} />
        <Stat label="Open deals" value={s ? String(s.open_deals) : '-'} />
        <Stat label="Open pipeline value" value={s ? formatCurrency(s.pipeline_value) : '-'} />
        <Stat label="Won this month" value={s ? String(s.won_this_month) : '-'} />
        <Stat label="Won value this month" value={s ? formatCurrency(s.won_value_this_month) : '-'} />
      </div>

      <section className="card">
        <h2>Pipeline by stage</h2>
        {board.isLoading && <p className="muted">Loading...</p>}
        <div className="bars">
          {board.data?.map((c) => (
            <div className="bar-row" key={c.stage}>
              <span className="bar-label">{c.label}</span>
              <div className="bar-track">
                <div className={`bar-fill stage-${c.stage}`} style={{ width: `${(c.count / maxCount) * 100}%` }} />
              </div>
              <span className="bar-value">
                {c.count} &middot; {formatCurrency(c.total_value)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
