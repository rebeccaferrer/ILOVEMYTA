import { useEffect, useState, type MouseEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  fetchChatHistory,
  fetchGarmentTypes,
  fetchProducts,
  formatPrice,
  type CatalogSearch,
  type ChatSearchState,
  type GarmentType,
  type ProductSummary,
} from '../api'
import {
  loadCardsPerRow,
  PHONE_CHOICES,
  saveCardsPerRow,
  WIDE_CHOICES,
  type CardsPerRow,
  type FromGalleryState,
  type RestoreScrollState,
} from '../gallery'

type Load<T> = { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: T }

// The last finished request; `data: null` means it failed. While the filter's
// request is still out, `result.key` is stale and the page shows "loading".
type Result<T> = { key: string; data: T | null }

// /products            every product
// /products?type=...   one category
// /products?chat=<id>  the shop assistant's search results from chat reply <id>
export default function ProductsPage() {
  const [searchParams] = useSearchParams()
  const chatId = searchParams.get('chat')
  const selectedType = chatId ? null : searchParams.get('type')
  const [types, setTypes] = useState<GarmentType[]>([])
  const [perRow, setPerRow] = useState<CardsPerRow>(loadCardsPerRow)

  function choosePerRow(value: CardsPerRow) {
    setPerRow(value)
    saveCardsPerRow(value)
  }

  useEffect(() => {
    const controller = new AbortController()
    fetchGarmentTypes(controller.signal).then(setTypes, () => {})
    return () => controller.abort()
  }, [])

  const selected = types.find((t) => t.garment_type === selectedType)

  const chips = (
    <nav className="filter-chips" aria-label="Product categories">
      <Link to="/products" className={`chip${selectedType || chatId ? '' : ' is-active'}`}>All</Link>
      {types.map((t) => (
        <Link
          key={t.garment_type}
          to={`/products?type=${encodeURIComponent(t.garment_type)}`}
          className={`chip${t.garment_type === selectedType ? ' is-active' : ''}`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  )

  return (
    <div className="section container">
      {chatId ? <ChatSearchView key={chatId} chatId={chatId} chips={chips} view={{ perRow, choosePerRow }} /> : (
        <>
          <h1 className="page-title">{selected ? selected.label : 'All Products'}</h1>
          {chips}
          <CatalogueResults garmentType={selectedType} label={selected?.label ?? 'All Products'}
            view={{ perRow, choosePerRow }} />
        </>
      )}
    </div>
  )
}

/** How the gallery is shown: the cards-per-row choice and how to change it. */
type View = { perRow: CardsPerRow; choosePerRow: (value: CardsPerRow) => void }

function CatalogueResults({ garmentType, label, view }: { garmentType: string | null; label: string; view: View }) {
  const key = garmentType ?? ''
  const [result, setResult] = useState<Result<ProductSummary[]> | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchProducts(key || null, controller.signal).then(
      (data) => setResult({ key, data }),
      (error) => { if (!controller.signal.aborted) { console.error(error); setResult({ key, data: null }) } },
    )
    return () => controller.abort()
  }, [key])

  const products: Load<ProductSummary[]> =
    result?.key !== key ? { status: 'loading' }
    : result.data ? { status: 'ready', data: result.data }
    : { status: 'error' }

  return (
    <ProductResults products={products} label={label} view={view}
      errorText="Products couldn't be loaded. Please try again in a moment." />
  )
}

/**
 * The chat search for this page. The chat widget hands it over in router state; after a reload
 * or from a bookmark it is read back from the shopper's saved chat, with current prices and stock.
 */
function useChatSearch(chatId: string): Load<CatalogSearch> {
  const state = useLocation().state as Partial<ChatSearchState> | null
  const fromState = state?.chatSearch && String(state.chatSearch.messageId) === chatId
    ? state.chatSearch.search : undefined
  const [saved, setSaved] = useState<CatalogSearch | null | undefined>(undefined)  // undefined = loading

  useEffect(() => {
    if (fromState) return
    let active = true
    fetchChatHistory().then(
      (history) => { if (active) setSaved(history.find((m) => String(m.id) === chatId)?.search ?? null) },
      () => { if (active) setSaved(null) },
    )
    return () => { active = false }
  }, [chatId, fromState])

  if (fromState) return { status: 'ready', data: fromState }
  return saved === undefined ? { status: 'loading' } : saved ? { status: 'ready', data: saved } : { status: 'error' }
}

// Keyed by chat id in ProductsPage, so each new search starts fresh.
function ChatSearchView({ chatId, chips, view }: { chatId: string; chips: ReactNode; view: View }) {
  const search = useChatSearch(chatId)
  const returning = (useLocation().state as Partial<RestoreScrollState> | null)?.restoreScrollY !== undefined

  // A new search from the chat replaces the page, so start at the top of it (unless the shopper
  // is coming back from a product, when ProductResults puts them back where they were).
  useEffect(() => { if (!returning) window.scrollTo({ top: 0 }) }, [returning])

  return (
    <>
      <div className="chat-search-heading">
        <p className="chat-search-eyebrow">Shop Assistant results</p>
        <h1 className="page-title">{search.status === 'ready' ? search.data.title : 'Your search'}</h1>
      </div>
      {chips}
      <ProductResults
        products={search.status === 'ready' ? { status: 'ready', data: search.data.products } : search}
        label={search.status === 'ready' ? search.data.title : 'your search'}
        view={view}
        errorText="These search results are no longer available. Ask the shop assistant again, or browse every product."
        countSuffix="found by the shop assistant"
      />
    </>
  )
}

function ProductResults({ products, label, view, errorText, countSuffix }: {
  products: Load<ProductSummary[]>
  label: string
  view: View
  errorText: string
  countSuffix?: string
}) {
  const location = useLocation()
  const restoreY = (location.state as Partial<RestoreScrollState> | null)?.restoreScrollY
  const ready = products.status === 'ready'

  // Back from a product page (its X button): return to the same spot in the gallery.
  useEffect(() => {
    if (ready && restoreY !== undefined) window.scrollTo({ top: restoreY })
  }, [ready, restoreY])

  if (products.status === 'loading') {
    return (
      <ul className="product-grid" data-per-row={view.perRow} aria-label="Loading products">
        {Array.from({ length: 8 }, (_, i) => (
          <li key={i} className="product-card is-placeholder" aria-hidden="true">
            <div className="product-card-image" />
            <div className="placeholder-line" />
            <div className="placeholder-line short" />
          </li>
        ))}
      </ul>
    )
  }
  if (products.status === 'error') {
    return <p className="notice" role="alert">{errorText}</p>
  }
  const count = products.data.length
  const from = location.pathname + location.search
  return (
    <>
      <div className="result-bar">
        <p className="result-count">
          {count} {count === 1 ? 'item' : 'items'}{countSuffix ? ` ${countSuffix}` : ''}
        </p>
        <PerRowPicker view={view} />
      </div>
      <ul className="product-grid" data-per-row={view.perRow}>
        {products.data.map((product) => (
          <li key={product.product_id}>
            <ProductCard product={product} from={from} label={label} />
          </li>
        ))}
      </ul>
    </>
  )
}

/** "Cards per row" buttons: Auto, 2, 3, 4, 5 on wider screens; 1 or 2 on phones (see index.css). */
function PerRowPicker({ view }: { view: View }) {
  const phoneValue = view.perRow === 1 ? 1 : 2  // on a phone, everything but 1 shows as 2 per row
  const button = (value: CardsPerRow, pressed: boolean) => (
    <button key={value} type="button" aria-pressed={pressed} onClick={() => view.choosePerRow(value)}
      aria-label={value === 'auto' ? 'Fit as many as the screen allows' : `${value} per row`}>
      {value === 'auto' ? 'Auto' : value}
    </button>
  )
  return (
    <div className="per-row" role="group" aria-label="Cards per row">
      <span className="per-row-label" aria-hidden="true">Cards per row</span>
      <span className="per-row-options per-row-wide">
        {WIDE_CHOICES.map((value) => button(value, view.perRow === value || (view.perRow === 1 && value === 2)))}
      </span>
      <span className="per-row-options per-row-phone">
        {PHONE_CHOICES.map((value) => button(value, phoneValue === value))}
      </span>
    </div>
  )
}

function ProductCard({ product, from, label }: { product: ProductSummary; from: string; label: string }) {
  const navigate = useNavigate()
  const to = `/products/${product.product_id}`

  // Note the gallery and how far down it the shopper is at the moment of the click, so the product
  // page's X can bring them back. Ctrl/Cmd/Shift-clicks still open a new tab or window as usual.
  function open(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    const state: FromGalleryState = { fromGallery: { path: from, label, scrollY: Math.round(window.scrollY) } }
    navigate(to, { state })
  }

  return (
    <Link to={to} onClick={open} className="product-card product-link">
      <img className="product-card-image" src={product.image_url} alt="" loading="lazy" />
      <h2 className="product-card-name">{product.name}</h2>
      <p className="product-card-price">{formatPrice(product.price_cents)}</p>
      <p className="product-card-text">{product.short_description}</p>
      {!product.in_stock && <p className="stock-badge is-out">Sold out</p>}
    </Link>
  )
}
