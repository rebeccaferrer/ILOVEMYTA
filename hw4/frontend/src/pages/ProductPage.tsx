import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  ApiError,
  createRestockAlert,
  deleteRestockAlert,
  fetchProduct,
  fetchRestockAlerts,
  formatPrice,
  NotFoundError,
  type ProductDetail,
  type RestockAlert,
} from '../api'
import { useAuth } from '../auth/AuthContext'
import { isGalleryPath, type FromGalleryState, type RestoreScrollState } from '../gallery'

const LOW_STOCK = 5

type Load = { status: 'loading' } | { status: 'missing' } | { status: 'error' } | { status: 'ready'; product: ProductDetail }

export default function ProductPage() {
  const { productId = '' } = useParams()
  // The last finished request, tagged with its product id; a stale id means "loading".
  const [result, setResult] = useState<{ productId: string; load: Load } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchProduct(productId, controller.signal).then(
      (product) => setResult({ productId, load: { status: 'ready', product } }),
      (error) => {
        if (controller.signal.aborted) return
        setResult({ productId, load: { status: error instanceof NotFoundError ? 'missing' : 'error' } })
      },
    )
    return () => controller.abort()
  }, [productId])

  const state: Load = result?.productId === productId ? result.load : { status: 'loading' }

  if (state.status === 'loading') {
    return <div className="section container"><p className="notice">Loading…</p></div>
  }
  if (state.status !== 'ready') {
    return (
      <div className="section container prose">
        <h1 className="page-title">{state.status === 'missing' ? 'Product not found' : 'Something went wrong'}</h1>
        <p>{state.status === 'missing' ? "We couldn't find that item." : "This product couldn't be loaded. Please try again in a moment."}</p>
        <p><Link to="/products" className="button button-primary">Back to products</Link></p>
      </div>
    )
  }

  return <ProductView product={state.product} />
}

/** Where the X goes: the gallery the shopper came from, or else this product's category. */
function useReturnTarget(product: ProductDetail): { path: string; label: string; scrollY: number } {
  const from = (useLocation().state as Partial<FromGalleryState> | null)?.fromGallery
  if (from && isGalleryPath(from.path)) {
    return { path: from.path, label: from.label, scrollY: from.scrollY }
  }
  return { path: `/products?type=${encodeURIComponent(product.garment_type)}`, label: product.garment_label, scrollY: 0 }
}

/** This shopper's restock alerts for one product, and ways to add or cancel one (logged in only). */
function useRestockAlerts(productId: string, signedIn: boolean) {
  const [alerts, setAlerts] = useState<RestockAlert[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!signedIn) return
    let active = true
    fetchRestockAlerts().then((all) => { if (active) setAlerts(all) }, () => {})
    return () => { active = false }
  }, [productId, signedIn])

  const forSize = (size: string) => alerts.find((a) => a.product_id === productId && a.size === size)

  async function add(size: string) {
    setMessage('')
    try {
      setAlerts(await createRestockAlert(productId, size))
      setMessage(`Done! If ${size} comes back in stock, you'll see a note here on the site.`)
    } catch (err) {
      setMessage(err instanceof ApiError ? err.messages[0] : "That didn't work. Please try again.")
    }
  }

  async function cancel(alert: RestockAlert) {
    setMessage('')
    setAlerts((current) => current.filter((a) => a.id !== alert.id))
    await deleteRestockAlert(alert.id).catch(() => {})
    setMessage(`Alert for ${alert.size} cancelled.`)
  }

  return { forSize, add, cancel, message }
}

function ProductView({ product }: { product: ProductDetail }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const signedIn = !!user && !user.must_change_password
  const restock = useRestockAlerts(product.product_id, signedIn)
  const back = useReturnTarget(product)
  const backState: RestoreScrollState = { restoreScrollY: back.scrollY }
  const inStock = product.sizes.filter((s) => s.quantity > 0)
  const colors = [product.primary_color, ...product.accent_colors]

  // Escape closes the product too, unless the shopper is typing or using the chat.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as Element | null
      if (event.key !== 'Escape' || event.defaultPrevented) return
      if (target?.closest('input, textarea, select, .chat-widget')) return
      navigate(back.path, { state: backState })
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  return (
    <div className="section container">
      <div className="product-topbar">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link to="/products">Products</Link>
          <span aria-hidden="true">/</span>
          <Link to={`/products?type=${encodeURIComponent(product.garment_type)}`}>{product.garment_label}</Link>
        </nav>
        <Link to={back.path} state={backState} className="product-close" aria-label={`Close and go back to ${back.label}`}
          title="Close (Esc)">
          <span className="product-close-label">Back to {back.label}</span>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </Link>
      </div>

      <div className="product-detail">
        <div className="product-detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div className="product-detail-info">
          <p className="eyebrow product-detail-type">{product.garment_label}</p>
          <h1 className="product-detail-name">{product.name}</h1>
          <p className="product-detail-price">{formatPrice(product.price_cents)}</p>
          <p className="product-detail-description">{product.description}</p>

          <dl className="product-facts">
            <dt>Color</dt>
            <dd>{colors.join(', ')}</dd>
          </dl>

          <h2 className="product-detail-heading">
            Sizes in stock
            <span className="product-detail-count">
              {inStock.length === 0 ? 'Sold out' : `${inStock.length} of ${product.sizes.length} sizes available`}
            </span>
          </h2>
          <ul className="size-list">
            {product.sizes.map((s) => {
              const alert = s.quantity === 0 ? restock.forSize(s.size) : undefined
              return (
                <li key={s.size} className={`size-chip${s.quantity === 0 ? ' is-out' : ''}`}>
                  <span className="size-chip-size">{s.size}</span>
                  <span className="size-chip-stock">
                    {s.quantity === 0 ? 'Sold out' : s.quantity <= LOW_STOCK ? `Only ${s.quantity} left` : 'In stock'}
                  </span>
                  {s.quantity === 0 && signedIn && (alert ? (
                    <button type="button" className="size-chip-alert is-on" onClick={() => restock.cancel(alert)}
                      aria-label={`Cancel the restock alert for ${s.size}`}>
                      ✓ Alert on
                    </button>
                  ) : (
                    <button type="button" className="size-chip-alert" onClick={() => restock.add(s.size)}
                      aria-label={`Notify me when ${s.size} is back in stock`}>
                      Notify me
                    </button>
                  ))}
                </li>
              )
            })}
          </ul>
          <p className="restock-note" role="status">
            {restock.message || (!signedIn && inStock.length < product.sizes.length && (
              <>
                Sold out in your size? <Link to="/login" state={{ from: location.pathname }}>Log in</Link> or{' '}
                <Link to="/create-account" state={{ from: location.pathname }}>create an account</Link> to get a
                restock alert.
              </>
            ))}
          </p>
        </div>
      </div>
    </div>
  )
}
