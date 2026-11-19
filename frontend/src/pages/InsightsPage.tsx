import { useQuery } from '@tanstack/react-query'
import { insightsApi } from '../api'
import { ErrorBox, PageHeader } from '../components/ui'
import { formatCurrency, humanize } from '../lib/format'
import { ago, days, monthLabel, num, percent } from '../lib/insights'

export default function InsightsPage() {
  const q = useQuery({ queryKey: ['insights'], queryFn: insightsApi.get, staleTime: 5 * 60_000 })
  const d = q.data

  return (
    <>
      <PageHeader
        title="Insights"
        action={d?.available && <span className="muted small">Updated {ago(d.refreshed_at)} · nightly Spark job</span>}
      />
      <ErrorBox error={q.error} />
      {q.isLoading && <p className="muted">Loading...</p>}

      {d && !d.available && (
        <div className="card empty">
          No insights yet. They are built by the nightly analytics job; to run it now:{' '}
          <code>docker compose --profile analytics run --rm analytics</code>
        </div>
      )}

      {d?.available && (
        <div className="insights">
          <section className="card">
            <h2>Market by suburb</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Suburb</th>
                    <th>Type</th>
                    <th>On market</th>
                    <th>Median asking</th>
                    <th>Per bedroom</th>
                    <th>Sold by us</th>
                    <th>Days to sell</th>
                  </tr>
                </thead>
                <tbody>
                  {d.suburb_market?.map((r) => (
                    <tr key={`${r.suburb}-${r.property_type}`}>
                      <td>{r.suburb}</td>
                      <td>{humanize(r.property_type)}</td>
                      <td>
                        {num(r.on_market)} <span className="muted small">of {num(r.listings)}</span>
                      </td>
                      <td>{formatCurrency(num(r.median_asking))}</td>
                      <td>{formatCurrency(num(r.avg_price_per_bedroom))}</td>
                      <td>
                        {num(r.deals_won)} {num(r.won_value) ? <span className="muted small">({formatCurrency(num(r.won_value))})</span> : null}
                      </td>
                      <td>{days(r.avg_days_to_close)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Lead sources</h2>
            <p className="muted small">Which channels bring deals that get to inspection and close.</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Deals</th>
                    <th>Reached inspection</th>
                    <th>Won / lost</th>
                    <th>Win rate</th>
                    <th>Won value</th>
                  </tr>
                </thead>
                <tbody>
                  {d.lead_funnel?.map((r) => (
                    <tr key={r.lead_source}>
                      <td>{r.lead_source}</td>
                      <td>{num(r.deals)}</td>
                      <td>
                        <Bar value={num(r.inspection_rate)} /> {percent(r.inspection_rate)}
                      </td>
                      <td>
                        {num(r.won)} / {num(r.lost)}
                      </td>
                      <td>{percent(r.win_rate)}</td>
                      <td>{formatCurrency(num(r.won_value))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Agent performance by month</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Agent</th>
                    <th>New deals</th>
                    <th>Won / lost</th>
                    <th>Win rate</th>
                    <th>Won value</th>
                    <th>Days to close</th>
                  </tr>
                </thead>
                <tbody>
                  {d.agent_performance?.map((r) => (
                    <tr key={`${r.month}-${r.agent}`}>
                      <td>{monthLabel(r.month)}</td>
                      <td>{r.agent}</td>
                      <td>{num(r.new_deals)}</td>
                      <td>
                        {num(r.won)} / {num(r.lost)}
                      </td>
                      <td>{percent(r.win_rate)}</td>
                      <td>{formatCurrency(num(r.won_value))}</td>
                      <td>{days(r.avg_days_to_close)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Time in each stage</h2>
            {d.stage_velocity?.length ? (
              <ul className="velocity">
                {d.stage_velocity.map((s) => (
                  <li key={s.stage}>
                    <strong>{humanize(s.stage)}</strong> {days(s.avg_days)}{' '}
                    <span className="muted small">({num(s.transitions)} moves)</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">Builds up as deals move between stages in the pipeline.</p>
            )}
          </section>
        </div>
      )}
    </>
  )
}

function Bar({ value }: { value: number | null }) {
  return (
    <span className="mini-bar" aria-hidden>
      <span style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
    </span>
  )
}
