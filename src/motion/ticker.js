import gsap from 'gsap'

/*
  data-ticker: an endless band of words that drifts sideways, as the marquees on
  landonorris.com do. Scrolling feeds it: it speeds up with scroll speed, leans
  into the motion, and reverses when you scroll back up.

    <div data-ticker><ul>...</ul></div>

  The list is cloned once (hidden from screen readers) so the loop is seamless.
  It only runs while on screen, and stands still for reduced motion.
*/
const BASE_SPEED = 55 // px per second when the page is still

export function initTicker({ lenis, reduced }) {
  document.querySelectorAll('[data-ticker]').forEach((track) => {
    const list = track.querySelector('ul')
    if (!list) return
    const clone = list.cloneNode(true)
    clone.setAttribute('aria-hidden', 'true')
    track.appendChild(clone)
    if (reduced) return

    let width = list.offsetWidth
    new ResizeObserver(() => {
      width = list.offsetWidth
    }).observe(list)

    let onScreen = false
    new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting
    }).observe(track)

    let x = 0
    let direction = -1
    let lean = 0
    gsap.ticker.add((time, deltaMs) => {
      if (!onScreen || !width) return
      const v = lenis ? lenis.velocity : 0
      if (v > 0.3) direction = -1
      else if (v < -0.3) direction = 1

      const speed = BASE_SPEED + Math.min(Math.abs(v) * 28, 1100)
      x += (direction * speed * Math.min(deltaMs, 50)) / 1000
      x = ((x % width) - width) % width // keep within one copy's width: [-width, 0)

      lean += (gsap.utils.clamp(-9, 9, -v * 0.22) - lean) * 0.12
      track.style.transform = `translate3d(${x.toFixed(2)}px, 0, 0) skewX(${lean.toFixed(2)}deg)`
    })
  })
}
