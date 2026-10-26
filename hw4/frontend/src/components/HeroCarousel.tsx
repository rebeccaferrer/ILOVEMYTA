import { useEffect, useState } from 'react'
import { SLIDES } from '../carouselPhotos'

const SECONDS_PER_SLIDE = 6

function prefersReducedMotion(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function HeroCarousel() {
  const [index, setIndex] = useState(0)
  // Rotation stops when the shopper presses pause, and never starts for reduced-motion users.
  const [playing, setPlaying] = useState(() => !prefersReducedMotion())
  // ...and waits while the pointer is over the photos or a control has keyboard focus.
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const count = SLIDES.length
  const rotating = playing && !hovered && !focused && count > 1

  useEffect(() => {
    if (!rotating) return
    const timer = window.setInterval(() => {
      if (!document.hidden) setIndex((i) => (i + 1) % count)
    }, SECONDS_PER_SLIDE * 1000)
    return () => window.clearInterval(timer)
  }, [rotating, count])

  if (count === 0) return null

  // Step from the latest photo (not the one shown at the last render), so quick double clicks both count.
  const step = (by: number) => setIndex((i) => (i + by + count) % count)

  return (
    <section
      className="hero-carousel"
      aria-roledescription="carousel"
      aria-label="Campus Customs photos"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false) }}
    >
      {/* While rotating on its own, screen readers aren't interrupted; when the shopper is
          in control, the new photo is announced. */}
      <div className="hero-carousel-slides" aria-live={rotating ? 'off' : 'polite'}>
        {SLIDES.map((slide, i) => (
          <img
            key={slide.file}
            className={`hero-carousel-slide${i === index ? ' is-active' : ''}`}
            src={slide.src}
            alt={slide.alt}
            style={{ objectPosition: slide.focus }}
            aria-hidden={i !== index}
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${count}: ${slide.alt}`}
            // All photos load up front (about 0.7 MB together) so none fades in half-loaded;
            // the first one comes first.
            fetchPriority={i === 0 ? 'high' : 'low'}
            decoding="async"
          />
        ))}
      </div>

      {count > 1 && (
        <>
          <button type="button" className="hero-carousel-arrow is-prev" onClick={() => step(-1)}
            aria-label="Previous photo">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"
                strokeLinejoin="round" />
            </svg>
          </button>
          <button type="button" className="hero-carousel-arrow is-next" onClick={() => step(1)}
            aria-label="Next photo">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path d="m9 5 7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"
                strokeLinejoin="round" />
            </svg>
          </button>

          <div className="hero-carousel-controls">
            <button type="button" className="hero-carousel-pause" onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? 'Pause the photo rotation' : 'Play the photo rotation'}>
              {playing ? (
                <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                  <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                  <path d="M8 5v14l11-7z" fill="currentColor" />
                </svg>
              )}
            </button>
            {SLIDES.map((slide, i) => (
              <button
                key={slide.file}
                type="button"
                className={`hero-carousel-dot${i === index ? ' is-active' : ''}`}
                onClick={() => setIndex(i)}
                aria-label={`Show photo ${i + 1} of ${count}`}
                aria-current={i === index}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
