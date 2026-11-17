import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'

/*
  Smooth scrolling. Lenis eases the real scroll position (the page still scrolls
  natively, so anchors, find-in-page and the scrollbar keep working) and is
  stepped by GSAP's ticker, which also steps ScrollTrigger and the WebGL stage.
  One clock means nothing drifts a frame behind anything else.

  The settings follow landonorris.com: lerp 0.1 for the wheel, and touch scrolling
  smoothed too (syncTouch) with a little extra throw, so phones get the same
  weighty glide as a trackpad.

  Returns null when the visitor prefers reduced motion; everything downstream
  works with native scrolling.
*/
export function initScroll({ reduced }) {
  if (reduced) return null

  const lenis = new Lenis({
    lerp: 0.1,
    smoothWheel: true,
    syncTouch: true,
    touchMultiplier: 1.25,
    anchors: true, // in-page links glide instead of jumping
  })

  lenis.on('scroll', ScrollTrigger.update)
  gsap.ticker.add((time) => lenis.raf(time * 1000))
  gsap.ticker.lagSmoothing(0)

  return lenis
}
