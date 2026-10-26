import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchDemandReport, type DemandReport } from '../api'
import { useAuth } from '../auth/AuthContext'

// Missed-demand report for Campus Customs managers (users.is_manager): what shoppers asked the
// chat for that the store couldn't supply. Anonymous: no names, emails or chat text.

const PERIODS = [7, 30, 90]
const dateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })

function shortDate(utc: string | null): string {
  return utc ? dateFormat.format(new Date(`${utc.replace(' ', 'T')}Z`)) : '—'
}

export default function ManagerPage() {
  const { user, checking } = useAuth()
  const [days, setDays] = useState(30)
  const [result, setResult] = useState<{ days: number; report: DemandReport | null } | null>(null)
  const isManager = !!user?.is_manager

  useEffect(() => {
    if (!isManager) return
    let active = true
    fetchDemandReport(days).then(
      (report) => { if (active) setResult({ days, report }) },
      () => { if (active) setResult({ days, report: null }) },
    )
    return () => { active = false }
  }, [days, isManager])

  if (checking) return null
  if (!isManager) {
    return (
      <div className="section container prose">
        <h1 className="page-title">Manager report</h1>
        <p>This page is for Campus Customs managers. {user ? '' : <><Link to="/login">Log in</Link> with a manager account.</>}</p>
      </div>
    )
  }

  const report = result?.days === days ? result.report : undefined

  return (
    <div className="section container manager">
      <p className="chat-search-eyebrow">Managers only</p>
      <h1 className="page-title">Missed demand</h1>
      <p className="manager-intro">
        What shoppers asked the shop assistant for that we couldn't supply. No names, emails or chat text are kept:
        only the search terms and products.
      </p>

      <div className="per-row manager-period" role="group" aria-label="Period">
        <span className="per-row-label" aria-hidden="true">Last</span>
        <span className="per-row-options">
          {PERIODS.map((d) => (
            <button key={d} type="button" aria-pressed={d === days} onClick={() => setDays(d)}>{d} days</button>
          ))}
        </span>
      </div>

      {report === undefined && <p className="notice">Loading…</p>}
      {report === null && <p className="notice" role="alert">The report couldn't be loaded. Please try again.</p>}
      {report && (
        <div className="manager-grid">
          <section>
            <h2 className="manager-heading">Searches with no results</h2>
            <p className="manager-help">Things shoppers looked for that we don't carry. Ideas for new products.</p>
            {report.unmet_searches.length === 0 ? <p className="manager-empty">None in this period.</p> : (
              <table className="manager-table">
                <thead><tr><th scope="col">Searched for</th><th scope="col">Times</th><th scope="col">Last</th></tr></thead>
                <tbody>
                  {report.unmet_searches.map((s) => (
                    <tr key={s.request}><td>{s.request}</td><td>{s.times}</td><td>{shortDate(s.last_asked)}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section>
            <h2 className="manager-heading">Sold-out sizes in demand</h2>
            <p className="manager-help">
              Sizes shoppers asked about while sold out, and how many are waiting for a restock alert. Reorder these first.
            </p>
            {report.sold_out_sizes.length === 0 ? <p className="manager-empty">None in this period.</p> : (
              <table className="manager-table">
                <thead>
                  <tr>
                    <th scope="col">Product</th><th scope="col">Size</th><th scope="col">Asked</th>
                    <th scope="col">Waiting</th><th scope="col">In stock now</th>
                  </tr>
                </thead>
                <tbody>
                  {report.sold_out_sizes.map((s) => (
                    <tr key={`${s.product_id}-${s.size}`}>
                      <td><Link to={`/products/${s.product_id}`}>{s.name}</Link></td>
                      <td>{s.size}</td>
                      <td>{s.times_asked}</td>
                      <td>{s.shoppers_waiting}</td>
                      <td>{s.in_stock_now > 0 ? <span className="manager-restocked">{s.in_stock_now} (restocked)</span> : 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
