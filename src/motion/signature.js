import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import strokes from '../data/signature-strokes.json'

/*
  The signature, written stroke by stroke.

  public/hero/signature.png is the real ink (white, on transparency).
  src/data/signature-strokes.json is the centre line of every pen stroke, in
  writing order, traced from that image by tools/signature/vectorize.py.

  Each element gets an inline SVG: a rect in currentColor, masked by the ink, and
  that masked by thick invisible strokes along the centre lines. Drawing those
  strokes (stroke-dashoffset) reveals the real ink as if the pen were moving.

    data-signature="intro"   written by the intro sequence (src/motion/intro.js)
    data-signature="scroll"  written as the footer scrolls into view, and unwritten
                             when it scrolls back (as on landonorris.com)

  Without JavaScript, CSS shows the whole signature through a plain mask
  (.signature in base.css).
*/

const SVG = 'http://www.w3.org/2000/svg'
const INK = '/hero/signature.png'
const SPEED = 2300 // image pixels per second, for letters
const FLOURISH_SPEED = 3800 // the closing swoops are quicker
const PEN_LIFT = 0.03 // seconds between strokes
let uid = 0

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(SVG, name)
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v)
  if (parent) parent.appendChild(node)
  return node
}

/** Build the SVG inside `host` once; returns its reveal paths in writing order. */
function mount(host) {
  if (host._signature) return host._signature
  const { width: w, height: h, inkWidth } = strokes
  const id = `sig-${++uid}`

  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, 'aria-hidden': 'true', focusable: 'false' })
  const defs = el('defs', {}, svg)

  const ink = el('mask', { id: `${id}-ink`, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: w, height: h }, defs)
  el('image', { href: INK, x: 0, y: 0, width: w, height: h }, ink)

  const reveal = el('mask', { id: `${id}-pen`, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: w, height: h }, defs)
  const pen = el(
    'g',
    {
      fill: 'none',
      stroke: '#fff',
      'stroke-width': Math.round(inkWidth * 2.6),
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
    },
    reveal,
  )

  const paths = strokes.strokes.map(({ k, p }) => {
    const node = el('path', { d: 'M' + p.map(([x, y]) => `${x} ${y}`).join('L') }, pen)
    const length = node.getTotalLength() || 1
    node.style.strokeDasharray = `${length} ${length + 1}`
    node.style.strokeDashoffset = length
    return { node, length, kind: k }
  })

  const group = el('g', { mask: `url(#${id}-pen)` }, svg)
  el('rect', { width: w, height: h, fill: 'currentColor', mask: `url(#${id}-ink)` }, group)

  host.appendChild(svg)
  host.classList.add('is-drawn-by-js')
  host._signature = paths
  return paths
}

/**
 * A paused timeline that writes the signature in `host`. Its duration follows the
 * length of the strokes; `speed` scales it (2 = twice as fast).
 */
export function signatureTimeline(host, { speed = 1 } = {}) {
  const paths = mount(host)
  const tl = gsap.timeline({ paused: true })
  let t = 0
  for (const { node, length, kind } of paths) {
    if (kind === 't') {
      // Short pieces at crossings go down with whatever is being written there.
      tl.to(node, { strokeDashoffset: 0, duration: 0.08, ease: 'none' }, Math.max(0, t - 0.08))
      continue
    }
    const pace = (kind === 'f' ? FLOURISH_SPEED : SPEED) * speed
    const duration = Math.max(0.05, length / pace)
    tl.to(node, { strokeDashoffset: 0, duration, ease: kind === 'f' ? 'power1.inOut' : 'none' }, t)
    t += duration + PEN_LIFT
  }
  gsap.set(host, { visibility: 'visible' })
  return tl
}

/** Show the whole signature at once (reduced motion). */
export function showSignature(host) {
  for (const { node } of mount(host)) node.style.strokeDashoffset = 0
  gsap.set(host, { visibility: 'visible' })
}

export function initSignatures({ reduced }) {
  document.querySelectorAll('[data-signature="scroll"]').forEach((host) => {
    if (reduced) return showSignature(host)
    const tl = signatureTimeline(host)
    // Tied to the scroll position with a little smoothing, so it writes as you
    // arrive at the footer and rewinds if you scroll back up.
    ScrollTrigger.create({
      trigger: host.closest('section, footer') || host,
      start: 'top 75%',
      end: 'bottom bottom',
      scrub: 0.5,
      animation: tl,
    })
  })
}
