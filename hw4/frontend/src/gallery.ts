// Shared by the product galleries (ProductsPage) and the single-item page (ProductPage).

/** Router state on a product card link: the gallery the shopper came from, so they can return to it. */
export type FromGalleryState = {
  fromGallery: {
    /** The gallery's address, e.g. "/products?type=hooded%20sweatshirt". */
    path: string
    /** Its heading, e.g. "Hoodies", for "Back to Hoodies". */
    label: string
    /** How far down the gallery they had scrolled. */
    scrollY: number
  }
}

/** Router state when returning to a gallery: scroll back to where the shopper was. */
export type RestoreScrollState = { restoreScrollY: number }

/** A gallery address is the Product page with an optional filter, never a single product. */
export function isGalleryPath(path: unknown): path is string {
  return typeof path === 'string' && /^\/products(\?[^/]*)?$/.test(path)
}

// --- Cards per row -----------------------------------------------------------------------------

/** 'auto' fits as many as the screen allows (about 5 on a laptop, 2 on a phone). */
export type CardsPerRow = 'auto' | 1 | 2 | 3 | 4 | 5

export const WIDE_CHOICES: CardsPerRow[] = ['auto', 2, 3, 4, 5]
export const PHONE_CHOICES: CardsPerRow[] = [1, 2]

const STORAGE_KEY = 'campusCustoms.cardsPerRow'

/** The shopper's last choice, remembered in this browser (falls back to 'auto'). */
export function loadCardsPerRow(): CardsPerRow {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    const value = saved === 'auto' ? 'auto' : Number(saved)
    return [...WIDE_CHOICES, ...PHONE_CHOICES].includes(value as CardsPerRow) ? (value as CardsPerRow) : 'auto'
  } catch {
    return 'auto'
  }
}

export function saveCardsPerRow(value: CardsPerRow): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    // Private browsing or blocked storage: the choice just isn't remembered.
  }
}
