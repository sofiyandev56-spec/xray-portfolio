import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import { signatureTimeline } from './signature.js'

const HOLD = 1 // seconds the finished autograph stays whole, long enough to be read at a glance

/*
  The one orchestrated moment on the page.

    0.0s   the page is a blueprint: the x-ray of the portrait on a grid
    0.2s   the autograph is signed across it, stroke by stroke, at the pace of
           a real hand (3.6s, set in tools/signature/pen_path.py)
    +HOLD  the finished autograph stays a moment, still on the blueprint where
           it reads best, while the photo starts to develop up from below
    then   it fades as the photo reaches it and the typeset name's lines rise
    +0.6s  the quieter pieces (navigation, role, hint) fade in

    data-intro="lines"       split into lines and raised
    data-intro="fade"        faded in
    data-signature="intro"   the autograph (data-ink="autograph")
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
  let develop = 0 // when the photo starts to develop
  let text = 0.9 // when the typeset name rises
  if (signature) {
    const write = signatureTimeline(signature)
    const length = write.duration()
    write.delay(0.2).play()
    const leave = 0.2 + length + HOLD
    gsap.to(signature, { autoAlpha: 0, duration: 0.7, ease: 'power2.out', delay: leave })
    develop = 0.2 + length
    text = leave + 0.1
  }

  if (hero) {
    gsap.fromTo(
      hero.uniforms.uReveal,
      { value: 0 },
      { value: 1, duration: 2.2, ease: 'power2.inOut', delay: develop },
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
          // Each mask is about 113% of its line's height and the capitals stand
          // a little above the line at this tight leading: start far enough
          // down that no sliver of them peeks out while waiting.
          yPercent: 130,
          duration: 1.1,
          ease: 'house',
          stagger: 0.1,
          delay: text,
        })
      },
    })
  })

  gsap.from('[data-intro="fade"]', {
    autoAlpha: 0,
    duration: 0.9,
    ease: 'power2.out',
    delay: text + 0.6,
    stagger: 0.1,
  })
}
