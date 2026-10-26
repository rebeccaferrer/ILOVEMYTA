import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const YEAR = new Date().getFullYear()

export default function SiteFooter() {
  const { user, checking, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <p className="footer-brand">CAMPUS CUSTOMS</p>
          <p className="footer-note">Yale apparel, with a shop assistant that answers from live stock and prices.</p>
        </div>
        <nav aria-label="Footer">
          <p className="footer-heading">Shop</p>
          <ul>
            <li><Link to="/products">All products</Link></li>
            <li><Link to="/about">About us</Link></li>
          </ul>
        </nav>
        <nav aria-label="Account">
          <p className="footer-heading">Account</p>
          {/* Matches the header: account links for the person who is (or isn't) logged in. */}
          {checking ? null : user ? (
            <ul>
              <li><Link to="/change-password">Change password</Link></li>
              {user.is_manager && <li><Link to="/manager">Manager report</Link></li>}
              <li>
                <button type="button" className="footer-link-button"
                  onClick={async () => { await logout(); navigate('/') }}>
                  Log out
                </button>
              </li>
            </ul>
          ) : (
            <ul>
              <li><Link to="/login">Log in</Link></li>
              <li><Link to="/create-account">Create account</Link></li>
            </ul>
          )}
        </nav>
      </div>
      <div className="container footer-legal">© {YEAR} Campus Customs</div>
    </footer>
  )
}
