import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import { signatureTimeline, showSignature } from './signature.js'

/*
  The one orchestrated moment on the page.

    0.0s   the page is a blueprint: the x-ray of the portrait on a grid
    0.2s   the signature is written across it, stroke by stroke
    ~55%   while the pen is still moving, the photo develops up behind it
    end    the signature fades; the name's lines rise
    +0.9s  the quieter pieces (navigation, role, hint) fade in

  Timings follow the signature's length, so a new signature keeps the rhythm.

    data-intro="lines"       split into lines and raised
    data-intro="fade"        faded in
    data-signature="intro"   the autograph
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
    const write = signatureTimeline(signature, { speed: 1.5 })
    const length = write.duration()
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
