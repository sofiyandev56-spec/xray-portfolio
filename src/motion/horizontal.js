import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

/*
  data-horizontal: a section that scrolls sideways while the page scrolls down.

    <section data-horizontal>
      <div data-horizontal-sticky>      stays put (CSS position: sticky)
        <div data-horizontal-track>     slides left as you scroll
          <article data-horizontal-item>...

  No GSAP pinning. The section is made as tall as the track is wide, the sticky
  child holds the viewport, and a scrubbed tween moves the track. Sticky is done
  by the browser's compositor, so it cannot jitter the way JS pinning can.

  Only on wide screens with motion allowed; otherwise the CSS leaves the items in
  a normal vertical stack.
*/
export function initHorizontal({ lenis } = {}) {
  const mm = gsap.matchMedia()

  mm.add('(min-width: 768px) and (prefers-reduced-motion: no-preference)', () => {
    const cleanups = []

    document.querySelectorAll('[data-horizontal]').forEach((section) => {
      const sticky = section.querySelector('[data-horizontal-sticky]')
      const track = section.querySelector('[data-horizontal-track]')
      if (!sticky || !track) return

      section.classList.add('is-horizontal')

      const overflow = () => Math.max(0, track.scrollWidth - window.innerWidth)
      const setHeight = () => {
        section.style.height = `${window.innerHeight + overflow()}px`
      }
      setHeight()

      const tween = gsap.to(track, {
        x: () => -overflow(),
        ease: 'none',
        scrollTrigger: {
          trigger: section,
          start: 'top top',
          end: 'bottom bottom',
          scrub: true,
          invalidateOnRefresh: true,
          onRefreshInit: setHeight,
        },
      })

      // Depth: each drawing drifts against the direction of travel, so it seems set
      // back inside its sheet (as the images in landonorris.com's sideways section do).
      const rem = () => parseFloat(getComputedStyle(document.documentElement).fontSize)
      track.querySelectorAll('.sheet__drawing > svg, .sheet__drawing img').forEach((art) => {
        gsap.fromTo(
          art,
          { x: () => -2.5 * rem() },
          {
            x: () => 2.5 * rem(),
            ease: 'none',
            scrollTrigger: {
              trigger: art.closest('[data-horizontal-item]'),
              containerAnimation: tween,
              start: 'left right',
              end: 'right left',
              scrub: true,
              invalidateOnRefresh: true,
            },
          },
        )
      })

      // Keyboard users tab to links that are off to the side. Scroll the page to
      // the point where that item is in view instead of leaving focus off-screen.
      const onFocus = (event) => {
        const item = event.target.closest('[data-horizontal-item]')
        const st = tween.scrollTrigger
        if (!item || !st || overflow() === 0) return
        const wanted = item.offsetLeft - window.innerWidth * 0.12
        const progress = gsap.utils.clamp(0, 1, wanted / overflow())
        const y = st.start + progress * (st.end - st.start)
        if (lenis) lenis.scrollTo(y, { duration: 0.8 })
        else window.scrollTo(0, y)
      }
      track.addEventListener('focusin', onFocus)

      cleanups.push(() => {
        track.removeEventListener('focusin', onFocus)
        section.classList.remove('is-horizontal')
        section.style.height = ''
        gsap.set(track, { clearProps: 'transform' })
      })
    })

    ScrollTrigger.refresh()
    return () => cleanups.forEach((cleanup) => cleanup())
  })
}
