import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import { signatureTimeline } from './signature.js'

const WRITE_SECONDS = 2.8

/*
  The one orchestrated moment on the page.

    0.0s   the page is a blueprint: the x-ray of the portrait on a grid
    0.2s   the name is handwritten across it in script, stroke by stroke
    ~50%   while the pen is still moving, the photo develops up behind it
    3.0s   the handwriting fades; the typeset name's lines rise
    +0.9s  the quieter pieces (navigation, role, hint) fade in

  The handwriting is fitted to WRITE_SECONDS however long its strokes are, so a
  different name or ink keeps the same rhythm.

    data-intro="lines"       split into lines and raised
    data-intro="fade"        faded in
    data-signature="intro"   the handwritten name (data-ink="name")
*/
export function playIntro({ stage, reduced }) {
  const root = document.documentElement
  const hero = stage?.scene('hero')
  const signature = document.querySelector('[data-signature="intro"]')

  root.classList.remove('is-loading')

  if (reduced) {
    if (hero) hero.uniforms.uReveal.value = 1
    if (signature) gsap.set(signature, { autoAlpha: 0 })
    return
  }

  // Everything after the signature is offset from it, so removing it tightens the intro.
  let start = 0
  if (signature) {
    const write = signatureTimeline(signature)
    write.timeScale(write.duration() / WRITE_SECONDS)
    const length = WRITE_SECONDS
    write.delay(0.2).play()
    gsap.to(signature, { autoAlpha: 0, duration: 0.7, ease: 'power2.out', delay: 0.2 + length + 0.35 })
    start = 0.2 + length * 0.5
  }

  if (hero) {
    gsap.fromTo(
      hero.uniforms.uReveal,
      { value: 0 },
      { value: 1, duration: 2.2, ease: 'power2.inOut', delay: start },
    )
  }

  document.querySelectorAll('[data-intro="lines"]').forEach((el) => {
    SplitText.create(el, {
      type: 'lines',
      mask: 'lines',
      linesClass: 'line',
      autoSplit: true,
      onSplit(self) {
        return gsap.from(self.lines, {
          yPercent: 110,
          duration: 1.1,
          ease: 'house',
          stagger: 0.1,
          delay: start + 0.9,
        })
      },
    })
  })

  gsap.from('[data-intro="fade"]', {
    autoAlpha: 0,
    duration: 0.9,
    ease: 'power2.out',
    delay: start + 1.8,
    stagger: 0.1,
  })
}
