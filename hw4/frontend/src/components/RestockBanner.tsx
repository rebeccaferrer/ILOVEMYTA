import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { deleteRestockAlert, fetchRestockAlerts, type RestockAlert } from '../api'
import { useAuth } from '../auth/AuthContext'

// "Good news!" banner under the header when a size the shopper asked about is back in stock.
// Checked on login and on every page change; dismissing it deletes the alert.

export default function RestockBanner() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [back, setBack] = useState<RestockAlert[]>([])
  const signedIn = !!user && !user.must_change_password

  useEffect(() => {
    if (!signedIn) return
    let active = true
    fetchRestockAlerts().then(
      (alerts) => { if (active) setBack(alerts.filter((a) => a.status === 'back')) },
      () => {},
    )
    return () => { active = false }
  }, [signedIn, pathname])

  if (!signedIn || back.length === 0) return null

  function dismiss(alert: RestockAlert) {
    setBack((current) => current.filter((a) => a.id !== alert.id))
    deleteRestockAlert(alert.id).catch(() => {})
  }

  return (
    <section className="restock-banner" aria-label="Back in stock">
      <div className="container">
        {back.map((alert) => (
          <div key={alert.id} className="restock-banner-item" role="status">
            <img src={alert.image_url} alt="" />
            <p>
              <strong>Good news!</strong> {alert.name} is back in stock in <strong>{alert.size}</strong>.
            </p>
            <Link to={`/products/${alert.product_id}`} className="restock-banner-view">View</Link>
            <button type="button" className="restock-banner-close" onClick={() => dismiss(alert)}
              aria-label={`Dismiss: ${alert.name} back in ${alert.size}`}>×</button>
          </div>
        ))}
      </div>
    </section>
  )
}
