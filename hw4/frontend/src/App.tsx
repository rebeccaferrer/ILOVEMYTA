import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import ChatWidget from './components/ChatWidget'
import RestockBanner from './components/RestockBanner'
import SiteFooter from './components/SiteFooter'
import SiteHeader from './components/SiteHeader'
import AboutPage from './pages/AboutPage'
import ChangePasswordPage from './pages/ChangePasswordPage'
import CreateAccountPage from './pages/CreateAccountPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import ManagerPage from './pages/ManagerPage'
import NotFoundPage from './pages/NotFoundPage'
import ProductPage from './pages/ProductPage'
import ProductsPage from './pages/ProductsPage'

export default function App() {
  const { user } = useAuth()
  const location = useLocation()
  // A shopper whose old password breaks today's rules must change it before going anywhere else.
  const mustChange = user?.must_change_password && location.pathname !== '/change-password'

  return (
    <div className="site">
      <SiteHeader />
      <RestockBanner />
      <main className="site-main">
        {mustChange ? (
          <Navigate to="/change-password" replace state={{ from: location.pathname }} />
        ) : (
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/products/:productId" element={<ProductPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/create-account" element={<CreateAccountPage />} />
            <Route path="/change-password" element={<ChangePasswordPage />} />
            <Route path="/manager" element={<ManagerPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        )}
      </main>
      <SiteFooter />
      <ChatWidget />
    </div>
  )
}
