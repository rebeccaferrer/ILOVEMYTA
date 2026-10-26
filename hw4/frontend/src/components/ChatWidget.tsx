import { Fragment, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import Markdown, { type Components } from 'react-markdown'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ApiError,
  chatSearchPath,
  fetchChatHistory,
  formatPrice,
  sendChatMessage,
  type ChatMessage,
  type ChatSearchState,
  type PageContext,
  type User,
} from '../api'
import { useAuth } from '../auth/AuthContext'

// Chat panel in the bottom-right corner, talking to the shop assistant agent (POST /api/chat).
// Anyone can chat. Logged-in shoppers' chats are saved and reloaded on every visit; a guest's
// chat lasts only for this visit, with a note offering Log In / Create Account to keep it.
// When a reply is a catalogue search, the Product page opens with the matching cards.

const MAX_MESSAGE_LENGTH = 1000
const PHONE_LAYOUT = '(max-width: 600px)'  // the chat panel covers the page here (see index.css)

const PRODUCT_PAGE = /^\/products\/([a-z0-9-]+)$/

/** The page context sent with each message: the address, and the product on a single-item page. */
function pageContext(pathname: string, search: string): PageContext {
  return { path: (pathname + search).slice(0, 200), product_id: PRODUCT_PAGE.exec(pathname)?.[1] ?? null }
}

// Saved times are UTC ("2026-10-25 18:04:11"); messages from this visit have none yet.
const dayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

function dayLabel(createdAt: string): string {
  const day = createdAt ? new Date(`${createdAt.replace(' ', 'T')}Z`) : new Date()
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (day.toDateString() === today.toDateString()) return 'Today'
  if (day.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return dayFormat.format(day)
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const { user, checking } = useAuth()

  return (
    <div className="chat-widget" onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false) }}>
      <section className="chat-panel" id="chat-panel" aria-label="Shop assistant chat" hidden={!open}>
        <header className="chat-header">
          <div>
            <p className="chat-title">Shop Assistant</p>
            <p className="chat-subtitle">Campus Customs</p>
          </div>
          <button type="button" className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
            ×
          </button>
        </header>
        {checking ? null : user?.must_change_password ? (
          <div className="chat-messages">
            <p className="chat-bubble is-assistant">Please choose a new password first, then I'll be glad to help.</p>
          </div>
        ) : (
          // Keyed by shopper, so logging in, out or switching accounts starts a fresh conversation.
          <Conversation key={user?.id ?? 'guest'} user={user} open={open} onClose={() => setOpen(false)} />
        )}
      </section>

      <button
        type="button"
        className="chat-launcher"
        aria-expanded={open}
        aria-controls="chat-panel"
        aria-label={open ? 'Close shop assistant chat' : 'Open shop assistant chat'}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? (
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
            <path
              d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.2 3.6A.5.5 0 0 1 5 19.2V16h-.5A.5.5 0 0 1 4 15.5z"
              fill="currentColor"
            />
          </svg>
        )}
      </button>
    </div>
  )
}

function GuestNotice() {
  const location = useLocation()
  return (
    <div className="chat-guest-note">
      <p>You're chatting as a guest, so this chat isn't saved after you leave.</p>
      <p>
        <Link to="/login" state={{ from: location.pathname }}>Log in</Link> or{' '}
        <Link to="/create-account" state={{ from: location.pathname }}>create a free account</Link> to keep your
        chat history.
      </p>
    </div>
  )
}

type Bubble = ChatMessage & { failed?: boolean }

function Conversation({ user, open, onClose }: { user: User | null; open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [messages, setMessages] = useState<Bubble[]>([])
  const [historyState, setHistoryState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [savedCount, setSavedCount] = useState(0)  // messages reloaded when the panel first opened
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const historyRequested = useRef(false)
  const nextLocalId = useRef(-1)  // negative ids for bubbles not saved on the server
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Load this shopper's saved conversation the first time the panel opens.
  useEffect(() => {
    if (!open || historyRequested.current) return
    historyRequested.current = true
    fetchChatHistory().then(
      (history) => {
        setMessages((current) => [...history, ...current])
        setSavedCount(history.length)
        setHistoryState('ready')
      },
      () => setHistoryState('error'),
    )
  }, [open])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, pending, open])

  // Put a reply's search results on the Product page. On a phone the panel covers the page, so
  // it only closes when the shopper asks to see the results.
  function showSearch(message: ChatMessage, closePanel: boolean) {
    if (!message.search) return
    const state: ChatSearchState = { chatSearch: { messageId: message.id, search: message.search } }
    navigate(chatSearchPath(message.id), { state })
    if (closePanel) onClose()
  }

  function localBubble(role: Bubble['role'], content: string, failed = false): Bubble {
    return { id: nextLocalId.current--, role, content, products: [], search: null, created_at: '', failed }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault()
    const text = draft.trim()
    if (!text || pending) return
    setMessages((current) => [...current, localBubble('user', text)])
    setDraft('')
    setPending(true)
    try {
      const reply = await sendChatMessage(text, pageContext(location.pathname, location.search))
      setMessages((current) => [...current, reply])
      showSearch(reply, false)
    } catch (err) {
      const message = err instanceof ApiError ? err.messages[0] : "I couldn't reach the shop assistant. Please try again."
      setMessages((current) => [...current, localBubble('assistant', message, true)])
    } finally {
      setPending(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) send(event)
  }

  const greeting = `Hi${user ? ` ${user.first_name}` : ''}! I'm the Campus Customs shop assistant. `
    + 'Ask me about products, sizes or prices.'

  return (
    <>
      {!user && <GuestNotice />}
      <div className="chat-messages" ref={listRef} role="log" aria-live="polite" aria-busy={pending}>
        {historyState === 'error' && (
          <p className="chat-bubble is-assistant is-error">Your earlier messages couldn't be loaded.</p>
        )}
        {historyState === 'ready' && messages.length === 0 && <p className="chat-bubble is-assistant">{greeting}</p>}
        {messages.map((m, i) => {
          const day = dayLabel(m.created_at)
          return (
            <Fragment key={m.id}>
              {(i === 0 || day !== dayLabel(messages[i - 1].created_at)) && <p className="chat-day">{day}</p>}
              <MessageBubble message={m} onShowSearch={() => showSearch(m, matchMedia(PHONE_LAYOUT).matches)} />
              {user && i === savedCount - 1 && (  // a guest's history is only this visit
                <p className="chat-welcome-back">Welcome back, {user?.first_name}! Your earlier chat is above.</p>
              )}
            </Fragment>
          )
        })}
        {pending && (
          <p className="chat-bubble is-assistant chat-typing" aria-label="The shop assistant is typing">
            <span /><span /><span />
          </p>
        )}
      </div>

      <form className="chat-composer" onSubmit={send}>
        <label className="visually-hidden" htmlFor="chat-input">Message</label>
        <textarea
          id="chat-input"
          ref={inputRef}
          rows={1}
          value={draft}
          maxLength={MAX_MESSAGE_LENGTH}
          placeholder="Ask about an item…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="submit" className="chat-send" disabled={!draft.trim() || pending} aria-label="Send message">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M3 20.5 21 12 3 3.5l.01 6.6L15 12 3.01 13.9z" fill="currentColor" />
          </svg>
        </button>
      </form>
    </>
  )
}

// Links in replies: site pages open in the app, anything else in a new tab.
const markdownComponents: Components = {
  a: ({ href = '', children }) =>
    href.startsWith('/') ? <Link to={href}>{children}</Link>
      : <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
}

function MessageBubble({ message, onShowSearch }: { message: Bubble; onShowSearch: () => void }) {
  if (message.role === 'user') {
    return <p className="chat-bubble is-user">{message.content}</p>
  }
  return (
    <div className="chat-reply">
      <div className={`chat-bubble is-assistant${message.failed ? ' is-error' : ''}`}>
        <Markdown components={markdownComponents}>{message.content}</Markdown>
      </div>
      {message.products.length > 0 && (
        <ul className="chat-products" aria-label="Products mentioned">
          {message.products.map((p) => (
            <li key={p.product_id}>
              <Link to={`/products/${p.product_id}`} className="chat-product">
                <img src={p.image_url} alt="" loading="lazy" />
                <span className="chat-product-name">{p.name}</span>
                <span className="chat-product-price">{formatPrice(p.price_cents)}</span>
                {!p.in_stock && <span className="chat-product-out">Sold out</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {message.search && (
        <button type="button" className="chat-see-all" onClick={onShowSearch}>
          See all {message.search.products.length} on the page →
        </button>
      )}
    </div>
  )
}
