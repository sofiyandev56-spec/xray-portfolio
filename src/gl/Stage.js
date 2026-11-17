import * as THREE from 'three'
import gsap from 'gsap'
import { HeroScene } from './scenes/HeroScene.js'
import { ContoursScene } from './scenes/ContoursScene.js'

/*
  One renderer, one fixed canvas, many scenes.

  Any element with data-gl="<name>" claims a region of the canvas. Every frame the
  stage asks each on-screen element for its bounding box and tells its scene to
  draw into exactly that rectangle (viewport + scissor), so WebGL content scrolls
  with the page like any other element.

  To add a scene: write a class with `constructor(stage, el)` and
  `render(rect, time, dt)`, then register it here.
*/
const SCENES = {
  hero: HeroScene,
  contours: ContoursScene,
}

export function isWebGL2Available() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(window.WebGL2RenderingContext && canvas.getContext('webgl2'))
  } catch {
    return false
  }
}

/** Colours come from the CSS custom properties in src/styles/tokens.css. */
function readTokens() {
  const css = getComputedStyle(document.documentElement)
  const color = (name) => new THREE.Color(css.getPropertyValue(name).trim())
  return {
    paper: color('--c-paper'),
    paperLine: color('--c-paper-line'),
    ink: color('--c-ink'),
    blue: color('--c-blue'),
    line: color('--c-line'),
    accent: color('--c-accent'),
  }
}

export class Stage {
  constructor(canvas, { reduced = false } = {}) {
    this.canvas = canvas
    this.reduced = reduced
    this.colors = readTokens()

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false, // scenes that need it render to multisampled targets
      powerPreference: 'high-performance',
    })
    this.renderer.setClearColor(0x000000, 0)
    this.renderer.autoClear = false

    // If the GPU drops the context (sleep, a driver reset, too many tabs), stop
    // drawing and fall back to the plain page: the photo and flat backgrounds.
    canvas.addEventListener('webglcontextlost', (event) => {
      event.preventDefault()
      this.stop()
      document.documentElement.classList.add('no-gl')
    })

    // Client-space pointer shared by every scene.
    this.pointer = { x: 0, y: 0, moved: false, lastMove: 0 }
    window.addEventListener('pointermove', this.onPointer, { passive: true })
    window.addEventListener('pointerdown', this.onPointer, { passive: true })

    this.scenes = []
    document.querySelectorAll('[data-gl]').forEach((el) => {
      const Scene = SCENES[el.dataset.gl]
      if (!Scene) {
        console.warn(`No WebGL scene is registered for data-gl="${el.dataset.gl}"`)
        return
      }
      this.scenes.push(new Scene(this, el))
    })

    this.resize()
    window.addEventListener('resize', this.resize)
  }

  /** Look up a scene by the value of its element's data-gl attribute. */
  scene(name) {
    return this.scenes.find((scene) => scene.name === name)
  }

  /**
   * Resolves when every scene has what it needs to draw. The built-in scenes are
   * procedural and resolve at once; a scene that loads models or textures should
   * return its loading promise from `ready()` so the intro waits for it.
   */
  ready() {
    return Promise.all(this.scenes.map((scene) => scene.ready?.()))
  }

  onPointer = (event) => {
    this.pointer.x = event.clientX
    this.pointer.y = event.clientY
    this.pointer.moved = true
    this.pointer.lastMove = performance.now()
  }

  resize = () => {
    this.width = window.innerWidth
    this.height = window.innerHeight
    // Retina sharpness costs fill rate; cap it harder on large screens.
    const cap = this.width > 768 ? 1.5 : 2
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, cap))
    this.renderer.setSize(this.width, this.height, false)
  }

  /** Draw a scene into the canvas region covered by `rect` (a DOMRect in client px). */
  drawToScreen(rect, scene, camera) {
    const r = this.renderer
    const bottom = this.height - rect.bottom
    r.setRenderTarget(null)
    r.setViewport(rect.left, bottom, rect.width, rect.height)
    r.setScissor(rect.left, bottom, rect.width, rect.height)
    r.setScissorTest(true)
    r.render(scene, camera)
  }

  tick = (time, deltaMs) => {
    const r = this.renderer
    r.setRenderTarget(null)
    r.setScissorTest(false)
    r.clear()

    const dt = deltaMs / 1000
    for (const scene of this.scenes) {
      const rect = scene.el.getBoundingClientRect()
      const offscreen =
        rect.width === 0 || rect.height === 0 || rect.bottom <= 0 || rect.top >= this.height
      if (offscreen) continue
      scene.render(rect, time, dt)
    }
  }

  /** Renders on GSAP's ticker so WebGL, tweens and smooth scroll share one frame. */
  start() {
    gsap.ticker.add(this.tick)
  }

  stop() {
    gsap.ticker.remove(this.tick)
  }
}
