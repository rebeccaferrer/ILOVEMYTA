// Client for the FastAPI backend (backend/main.py). Vite proxies /api and /images to it.

export type GarmentType = {
  garment_type: string
  label: string
  product_count: number
}

export type ProductSummary = {
  product_id: string
  name: string
  garment_type: string
  garment_label: string
  short_description: string
  price_cents: number
  image_url: string
  in_stock: boolean
}

export type SizeStock = {
  size: string
  quantity: number
}

export type ProductDetail = ProductSummary & {
  description: string
  primary_color: string
  accent_colors: string[]
  sizes: SizeStock[]
  total_stock: number
}

export class NotFoundError extends Error {}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (response.status === 404) throw new NotFoundError(path)
  if (!response.ok) throw new Error(`${path} failed with ${response.status}`)
  return response.json() as Promise<T>
}

export const fetchGarmentTypes = (signal?: AbortSignal) => getJson<GarmentType[]>('/api/garment-types', signal)

export const fetchProducts = (garmentType: string | null, signal?: AbortSignal) =>
  getJson<ProductSummary[]>(
    garmentType ? `/api/products?type=${encodeURIComponent(garmentType)}` : '/api/products',
    signal,
  )

export const fetchProduct = (productId: string, signal?: AbortSignal) =>
  getJson<ProductDetail>(`/api/products/${encodeURIComponent(productId)}`, signal)

// --- Accounts --------------------------------------------------------------------------------

export type User = {
  id: number
  first_name: string
  last_name: string
  email: string
  /** The password predates today's rules and breaks them; it must be changed before shopping. */
  must_change_password: boolean
  /** Can see the missed-demand report (/manager). */
  is_manager: boolean
}

export type SignupInput = {
  first_name: string
  last_name: string
  email: string
  password: string
}

/** An API error with plain-language messages, and the form field they belong to (if any). */
export class ApiError extends Error {
  readonly status: number
  readonly field: string | null
  readonly messages: string[]

  constructor(status: number, field: string | null, messages: string[]) {
    super(messages.join(' '))
    this.status = status
    this.field = field
    this.messages = messages
  }
}

const FIELD_NAMES: Record<string, string> = {
  first_name: 'first_name', last_name: 'last_name', email: 'email', password: 'password',
  current_password: 'current_password', new_password: 'new_password',
}

async function toApiError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({}))
  const detail = body?.detail
  if (typeof detail === 'string') return new ApiError(response.status, null, [detail])
  if (detail && !Array.isArray(detail) && detail.field) {
    return new ApiError(response.status, detail.field, detail.messages)
  }
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation error: [{ loc: ['body', 'email'], msg }]
    const field = FIELD_NAMES[detail[0]?.loc?.at(-1)] ?? null
    const message = field === 'email' ? 'Enter a valid email address.'
      : field === 'first_name' || field === 'last_name' ? 'Enter a name of 1 to 50 characters, without < or >.'
      : 'Please check the form and try again.'
    return new ApiError(response.status, field, [message])
  }
  return new ApiError(response.status, null, ['Something went wrong. Please try again in a moment.'])
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (!response.ok) throw await toApiError(response)
  return (response.status === 204 ? undefined : await response.json()) as T
}

export const signup = (input: SignupInput) => postJson<User>('/api/auth/signup', input)
export const login = (email: string, password: string) => postJson<User>('/api/auth/login', { email, password })
export const logout = () => postJson<void>('/api/auth/logout')
export const changePassword = (current_password: string, new_password: string) =>
  postJson<User>('/api/auth/change-password', { current_password, new_password })

export async function fetchCurrentUser(): Promise<User | null> {
  const response = await fetch('/api/auth/me', { credentials: 'same-origin' })
  if (response.status === 401) return null
  if (!response.ok) throw await toApiError(response)
  return response.json() as Promise<User>
}

// --- Shop assistant chat ---------------------------------------------------------------------

/** A chat reply's catalogue search: the website shows these cards on the Product page. */
export type CatalogSearch = {
  /** Heading written by the shop assistant, e.g. "Navy hoodies". */
  title: string
  /** Every matching product (up to 12), best match first, with live prices and stock. */
  products: ProductSummary[]
}

export type ChatMessage = {
  id: number
  role: 'user' | 'assistant'
  content: string
  /** Cards shown inside the chat panel. For a search reply, the first 3 search results. */
  products: ProductSummary[]
  /** Set when the reply is a catalogue search; null for every other message. */
  search: CatalogSearch | null
  created_at: string
}

/** Router state that hands a chat search to the Product page (/products?chat=<message id>). */
export type ChatSearchState = { chatSearch: { messageId: number; search: CatalogSearch } }

export const chatSearchPath = (messageId: number) => `/products?chat=${messageId}`

export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const response = await fetch('/api/chat/history', { credentials: 'same-origin' })
  if (!response.ok) throw await toApiError(response)
  return response.json() as Promise<ChatMessage[]>
}

/** Where the shopper is when they send a message, so the assistant knows what "this" means. */
export type PageContext = {
  /** The address after the domain, e.g. "/products/basic-hoodie-big-yale". */
  path: string
  /** The product on a single-item page, if any. */
  product_id: string | null
}

export const sendChatMessage = (message: string, page: PageContext) =>
  postJson<ChatMessage>('/api/chat', { message, page })

// --- Restock alerts and the manager report (insights.py) ---------------------------------------

export type RestockAlert = {
  id: number
  product_id: string
  name: string
  size: string
  image_url: string
  /** 'waiting' while the size is sold out; 'back' once it's in stock again. */
  status: 'waiting' | 'back'
  created_at: string
}

async function getAuthed<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin' })
  if (!response.ok) throw await toApiError(response)
  return response.json() as Promise<T>
}

export const fetchRestockAlerts = () => getAuthed<RestockAlert[]>('/api/restock-alerts')

export const createRestockAlert = (product_id: string, size: string) =>
  postJson<RestockAlert[]>('/api/restock-alerts', { product_id, size })

export async function deleteRestockAlert(id: number): Promise<void> {
  const response = await fetch(`/api/restock-alerts/${id}`, { method: 'DELETE', credentials: 'same-origin' })
  if (!response.ok) throw await toApiError(response)
}

export type DemandReport = {
  days: number
  unmet_searches: { request: string; times: number; last_asked: string }[]
  sold_out_sizes: {
    product_id: string
    name: string
    size: string
    times_asked: number
    shoppers_waiting: number
    in_stock_now: number
    last_asked: string | null
  }[]
}

export const fetchDemandReport = (days: number) => getAuthed<DemandReport>(`/api/manager/demand-report?days=${days}`)

// --- Formatting ------------------------------------------------------------------------------

const priceFormat = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function formatPrice(cents: number): string {
  return priceFormat.format(cents / 100)
}
