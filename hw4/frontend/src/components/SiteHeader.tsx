import { useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const MAIN_LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Product', end: false },
  { to: '/about', label: 'About Us', end: false },
]

export default function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { user, checking, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [lastPath, setLastPath] = useState(location.pathname)

  // Close the mobile menu after navigating.
  if (location.pathname !== lastPath) {
    setLastPath(location.pathname)
    setMenuOpen(false)
  }

  return (
    <header className="site-header">
      <div className="announcement">Yale apparel for students, alumni &amp; families</div>
      <div className="header-bar container">
        <Link to="/" className="wordmark" aria-label="Campus Customs home">
          <span className="wordmark-top">CAMPUS</span>
          <span className="wordmark-bottom">CUSTOMS</span>
          <span className="wordmark-tag">Yale Apparel</span>
        </Link>

        <button
          type="button"
          className="menu-toggle"
          aria-expanded={menuOpen}
          aria-controls="site-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="menu-toggle-bars" aria-hidden="true" />
          <span className="visually-hidden">Menu</span>
        </button>

        <nav id="site-nav" className={`site-nav${menuOpen ? ' is-open' : ''}`} aria-label="Main">
          <ul className="nav-main">
            {MAIN_LINKS.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} end={link.end} className="nav-link">
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
          {user ? (
            <ul className="nav-account">
              <li className="nav-greeting">Hi, {user.first_name}</li>
              <li>
                <button
                  type="button"
                  className="nav-link nav-button"
                  onClick={async () => { await logout(); navigate('/') }}
                >
                  Log Out
                </button>
              </li>
            </ul>
          ) : (
            <ul className={`nav-account${checking ? ' is-checking' : ''}`}>
              <li>
                <NavLink to="/login" state={{ from: location.pathname }} className="nav-link">
                  Log In
                </NavLink>
              </li>
              <li>
                <NavLink to="/create-account" state={{ from: location.pathname }} className="button button-primary nav-cta">
                  Create Account
                </NavLink>
              </li>
            </ul>
          )}
        </nav>
      </div>
    </header>
  )
}
