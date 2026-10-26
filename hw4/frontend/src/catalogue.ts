// Shop categories, matching the garment_types lookup table in campus_customs.db.
// Product listings themselves will come from the shop API once it exists.

const productImages = import.meta.glob<string>('../../data/data/products/*.jpg', {
  eager: true,
  import: 'default',
})

export function productImage(productId: string): string | undefined {
  return productImages[`../../data/data/products/${productId}.jpg`]
}

export type Category = {
  garmentType: string
  label: string
  sampleProductId: string
}

// The first six are shown on the home page.
export const CATEGORIES: Category[] = [
  { garmentType: 'hooded sweatshirt', label: 'Hoodies', sampleProductId: 'the-forest-school-hoodie' },
  { garmentType: 'crewneck sweatshirt', label: 'Crewneck Sweatshirts', sampleProductId: 'champion-reverse-weave-crewneck' },
  { garmentType: 't-shirt', label: 'T-Shirts', sampleProductId: 'yale-bowl-t-shirt' },
  { garmentType: 'quarter-zip pullover', label: 'Quarter-Zips', sampleProductId: 'school-of-medicine-1-4-zip' },
  { garmentType: 'fleece jacket', label: 'Fleece Jackets', sampleProductId: 'saybrook-sweater-fleece-jacket' },
  { garmentType: 'full-zip hooded sweatshirt', label: 'Full-Zip Hoodies', sampleProductId: 'champion-full-zip-hood' },
  { garmentType: 'long-sleeve shirt', label: 'Long-Sleeve Shirts', sampleProductId: 'ua-mens-tech-l-s-2-0' },
  { garmentType: 'jacket', label: 'Jackets', sampleProductId: 'brooks-brothers-bomber-jacket-yale' },
  { garmentType: 'mock-neck pullover', label: 'Mock-Necks', sampleProductId: 'yale-maplehouse-diana-mockneck' },
]
