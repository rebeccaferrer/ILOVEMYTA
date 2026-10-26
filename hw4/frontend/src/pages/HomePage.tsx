import { Link } from 'react-router-dom'
import { CATEGORIES, productImage } from '../catalogue'
import { SLIDES } from '../carouselPhotos'
import HeroCarousel from '../components/HeroCarousel'

// The banner rotates through the photos in hw4/images/ (HeroCarousel). With no photos there,
// it falls back to the navy banner with a product photo.
const HAS_PHOTOS = SLIDES.length > 0

const FEATURES = [
  { title: 'Live stock by size', text: 'See which sizes are on the shelf right now, from XS to XXL.' },
  { title: 'Ask the shop assistant', text: 'Chat about any item and get true answers on stock and prices.' },
  { title: 'Find matching items', text: 'Describe what you want and see the products that fit.' },
]

export default function HomePage() {
  return (
    <>
      <div className={HAS_PHOTOS ? 'hero hero-photo' : 'hero'}>
        {HAS_PHOTOS && <HeroCarousel />}
        <div className="container hero-inner">
          <div className="hero-copy">
            <p className="eyebrow">Campus Customs</p>
            <h1>Wear your Yale pride</h1>
            <p className="hero-text">
              Hoodies, crewnecks, tees and quarter-zips for every college, school, sport and family member.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="button button-light">Shop products</Link>
              <Link to="/create-account" className="button button-outline-light">Create account</Link>
            </div>
          </div>
          {!HAS_PHOTOS && (
            <img className="hero-image" src={productImage('champion-reverse-weave-hoodie-1')} alt="Navy Yale hoodie" />
          )}
        </div>
      </div>

      <section className="section container">
        <h2 className="section-title">Shop by category</h2>
        <ul className="category-grid">
          {CATEGORIES.slice(0, 6).map((category) => (
            <li key={category.garmentType}>
              <Link to={`/products?type=${encodeURIComponent(category.garmentType)}`} className="category-card">
                <img src={productImage(category.sampleProductId)} alt="" loading="lazy" />
                <span>{category.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="section section-tint">
        <div className="container feature-grid">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="feature">
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}
