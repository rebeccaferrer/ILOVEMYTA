// Home-page banner photos: every .jpg in hw4/images/, in file-name order. Add a photo there and
// it joins the rotation (run trim_carousel_images.py first if it has white bars).
const PHOTO_FILES = import.meta.glob<string>('../../images/*.jpg', { eager: true, import: 'default' })

// Descriptions for screen readers, and where to keep the crop so faces stay in view.
// Photos not listed here get a general description and a centered crop.
const PHOTO_DETAILS: Record<string, { alt: string; focus: string }> = {
  'image-1.jpg': {
    alt: 'A mother in a Yale Mother quarter-zip smiles at her son in a Yale T-shirt and cap on the Yale campus in autumn',
    focus: '55% 30%',
  },
  'image-2.jpg': {
    alt: 'A group of smiling students in Yale hoodies and T-shirts at a Yale football game',
    focus: '50% 30%',
  },
  'image-3.jpg': {
    alt: 'A bulldog in a navy Yale harness standing outside a shop with a blue awning',
    focus: '50% 45%',
  },
  'image-4.jpg': {
    alt: 'Three women in Yale School of Management quarter-zips and sweaters talking at a table',
    focus: '55% 35%',
  },
}

export const SLIDES = Object.entries(PHOTO_FILES)
  .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
  .map(([path, src]) => {
    const file = path.split('/').pop() ?? path
    const details = PHOTO_DETAILS[file] ?? { alt: 'Shoppers in Campus Customs Yale apparel', focus: '50% 40%' }
    return { file, src, ...details }
  })
