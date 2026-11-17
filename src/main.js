import '@fontsource-variable/anybody/wdth.css'
import '@fontsource-variable/newsreader/opsz.css'
import '@fontsource-variable/newsreader/opsz-italic.css'
import 'lenis/dist/lenis.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/sections.css'

import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'
import { CustomEase } from 'gsap/CustomEase'

import { Stage, isWebGL2Available } from './gl/Stage.js'
import { initScroll } from './motion/scroll.js'
import { initHorizontal } from './motion/horizontal.js'
import { initNavTheme } from './motion/navTheme.js'
import { initSplit } from './motion/splitText.js'
import { initSignatures, signatureTimeline } from './motion/signature.js'
import { initRoll } from './motion/roll.js'
import { initTicker } from './motion/ticker.js'
import { playIntro } from './motion/intro.js'

gsap.registerPlugin(ScrollTrigger, SplitText, CustomEase)
// The same curve as --ease in tokens.css, so CSS and JS motion feel like one hand.
CustomEase.create('house', '0.7, 0, 0.2, 1')

const root = document.documentElement
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Text is measured and split into lines, so the real fonts must be in before that happens. */
function loadFonts() {
  const wanted = [
    '800 1em "Anybody Variable"',
    '400 1em "Newsreader Variable"',
    'italic 400 1em "Newsreader Variable"',
  ]
  const loaded = Promise.all(wanted.map((font) => document.fonts.load(font)))
  const timeout = new Promise((resolve) => setTimeout(resolve, 3000))
  return Promise.race([loaded, timeout])
}

/*
  Boot order:
    1. Start WebGL first, so shaders compile while the fonts download.
    2. Wait for fonts and for every scene's assets.
    3. Wire up scrolling and the attribute-driven behaviours.
    4. Start rendering, then play the one intro sequence.
*/
async function boot() {
  let stage = null
  if (isWebGL2Available()) {
    try {
      stage = new Stage(document.querySelector('canvas.gl'), { reduced })
    } catch (error) {
      console.warn('WebGL failed to start; continuing without it.', error)
    }
  }
  // Without WebGL the sections fall back to their flat CSS backgrounds.
  if (!stage) root.classList.add('no-gl')

  await Promise.all([loadFonts(), stage?.ready()])

  const lenis = initScroll({ reduced })
  initHorizontal({ lenis })
  initNavTheme()
  initSplit({ reduced })
  initSignatures({ reduced })
  initRoll({ reduced })
  initTicker({ lenis, reduced })

  stage?.start()
  ScrollTrigger.refresh()
  playIntro({ stage, reduced })

  // A handle for poking at things from the console while developing.
  if (import.meta.env.DEV) window.__portfolio = { stage, lenis, gsap, ScrollTrigger, signatureTimeline }
}

boot().catch((error) => {
  console.error(error)
  root.classList.remove('is-loading')
  root.classList.add('boot-failed')
})
