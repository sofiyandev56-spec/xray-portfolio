import * as THREE from 'three'
import { Fluid } from '../Fluid.js'
import { IdleCursor } from '../IdleCursor.js'
import { snoise, lines, fullscreenVert } from '../noise.glsl.js'

/*
  The hero: one picture in two states, and a mask that chooses between them.

    surface    the portrait cut-out on paper with contour lines
    blueprint  an x-ray aligned to the same picture (skull and skeleton, the
               MacBook's interior with its M4 chip) on a drafting grid
    mask       dye stirred by the cursor in a small fluid simulation (Fluid),
               plus the intro wipe

  Markup:

    <div data-gl="hero" data-gl-overlay="/hero/xray.webp"></div>
    <img data-gl-subject src="/hero/portrait.webp" ...>

  The <img> is the layout handle. CSS positions and sizes it; this scene reads its
  box every frame and draws both textures exactly there, so the portrait responds
  to breakpoints like any other element. The <img> itself stays hidden unless
  WebGL is unavailable, when it becomes the fallback.

  The two images must share the same frame: public/hero/xray.webp is built over
  public/hero/portrait.webp (843 x 818) by tools/xray/build.py. If you change the
  photo, re-measure the positions at the top of that script and rebuild.
*/

const compositeFrag = /* glsl */ `
uniform sampler2D tPhoto;
uniform sampler2D tXray;
uniform sampler2D tTrail;
uniform vec4 uSubject;   // x, y, width, height of the portrait in this element's uv space
uniform vec2 uShift;     // parallax offset in portrait uv
uniform float uHasSubject;
uniform float uTime;
uniform float uReveal;
uniform float uAspect;
uniform vec3 uPaper;
uniform vec3 uPaperLine;
uniform vec3 uBlue;
uniform vec3 uBlueLine;
uniform vec3 uAccent;
varying vec2 vUv;

${snoise}
${lines}

void main() {
  // p keeps the noise and grid square whatever the element's shape.
  vec2 p = vec2(vUv.x * uAspect, vUv.y);

  // Paper world: a slow contour field, like the lines of a topographic map.
  float field = snoise(vec3(p * 1.15, uTime * 0.035)) * 0.5 + 0.5;
  vec3 paper = mix(uPaper, uPaperLine, isoLines(field, 9.0));

  // Blueprint world: a drafting grid, heavier every fourth line.
  float grid = max(gridLines(p * 24.0) * 0.28, gridLines(p * 6.0) * 0.55);
  vec3 blue = mix(uBlue, uBlueLine, grid * 0.6);

  // The portrait and its drawing, sampled in the portrait's own uv.
  vec2 suv = (vUv - uSubject.xy) / uSubject.zw + uShift;
  float inside = step(0.0, suv.x) * step(suv.x, 1.0) * step(0.0, suv.y) * step(suv.y, 1.0);
  inside *= uHasSubject;
  vec4 photo = texture2D(tPhoto, suv) * inside;
  vec4 xray = texture2D(tXray, suv) * inside;

  vec3 surface = mix(paper, photo.rgb, photo.a);
  vec3 blueprint = mix(blue, xray.rgb, xray.a);

  // Mask field: positive inside the blueprint. Two sources, whichever is larger.
  float trail = texture2D(tTrail, vUv).r;
  trail += snoise(vec3(p * 6.0, uTime * 0.25)) * 0.07 * smoothstep(0.02, 0.3, trail);
  float wake = trail - 0.26;

  // The intro: the sheet "develops" from the bottom edge upward as uReveal goes 0 -> 1.
  float front = mix(-0.25, 1.3, uReveal);
  float develop = vUv.y + snoise(vec3(p.x * 1.4, 2.0, uTime * 0.12)) * 0.07 - front;

  float field2 = max(wake, develop);

  // Distance to the mask's edge in pixels gives a crisp boundary and a rim of constant width.
  float px = field2 / max(fwidth(field2), 1e-5);
  float mask = smoothstep(-1.0, 1.0, px);
  float rim = 1.0 - smoothstep(1.0, 2.6, abs(px));

  vec3 color = mix(surface, blueprint, mask);
  color = mix(color, uAccent, rim);

  gl_FragColor = vec4(color, 1.0);
  #include <colorspace_fragment>
}
`

export class HeroScene {
  name = 'hero'

  constructor(stage, el) {
    this.stage = stage
    this.el = el
    const { renderer, colors } = stage

    this.subjectEl = el.parentElement.querySelector('[data-gl-subject]')

    this.fluid = new Fluid()
    this.idle = stage.reduced ? null : new IdleCursor()
    this.from = new THREE.Vector2(0.5, 0.5)
    this.to = new THREE.Vector2(0.5, 0.5)
    this.wasIdle = true
    this.tilt = new THREE.Vector2()
    this.aspect = 1

    this.uniforms = {
      tPhoto: { value: null },
      tXray: { value: null },
      tTrail: { value: null },
      uSubject: { value: new THREE.Vector4(0, 0, 1, 1) },
      uShift: { value: new THREE.Vector2() },
      uHasSubject: { value: 0 },
      uTime: { value: 0 },
      uReveal: { value: stage.reduced ? 1 : 0 }, // src/motion/intro.js tweens this to 1
      uAspect: { value: 1 },
      uPaper: { value: colors.paper },
      uPaperLine: { value: colors.paperLine },
      uBlue: { value: colors.blue },
      uBlueLine: { value: colors.line },
      uAccent: { value: colors.accent },
    }

    this.scene = new THREE.Scene()
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    this.scene.add(
      new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        new THREE.ShaderMaterial({
          uniforms: this.uniforms,
          vertexShader: fullscreenVert,
          fragmentShader: compositeFrag,
          depthTest: false,
          depthWrite: false,
        }),
      ),
    )

    // Load the pair of images. The intro waits on this promise (see Stage.ready).
    const loader = new THREE.TextureLoader()
    const load = async (url) => {
      const texture = await loader.loadAsync(url)
      texture.colorSpace = THREE.SRGBColorSpace
      texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy())
      return texture
    }
    const photoUrl = this.subjectEl?.currentSrc || this.subjectEl?.src
    const overlayUrl = el.dataset.glOverlay
    this.loading =
      photoUrl && overlayUrl
        ? Promise.all([load(photoUrl), load(overlayUrl)])
            .then(([photo, xray]) => {
              this.uniforms.tPhoto.value = photo
              this.uniforms.tXray.value = xray
              this.uniforms.uHasSubject.value = 1
            })
            .catch((error) => {
              console.warn('Hero images failed to load; drawing the background only.', error)
            })
        : Promise.resolve()
  }

  ready() {
    return this.loading
  }

  /** Where the portrait sits inside this element, as x, y, width, height in uv (y up). */
  measureSubject(rect) {
    if (!this.subjectEl) return
    const box = this.subjectEl.getBoundingClientRect()
    if (box.width === 0 || box.height === 0) return
    this.uniforms.uSubject.value.set(
      (box.left - rect.left) / rect.width,
      1 - (box.bottom - rect.top) / rect.height,
      box.width / rect.width,
      box.height / rect.height,
    )
  }

  /**
   * Where the brush is this frame, in this element's uv space, and how much it
   * stirs. The real pointer leads; after two quiet seconds IdleCursor takes over.
   */
  updateBrush(rect) {
    const { pointer } = this.stage
    const idle = this.idle ? this.idle.update(pointer) : false

    let u = this.to.x
    let v = this.to.y
    let weight = 0

    if (idle) {
      // A lighter, thinner stroke than a real cursor: a hint, not a takeover.
      const s = this.uniforms.uSubject.value
      u = s.x + s.z * this.idle.point.x
      v = s.y + s.w * this.idle.point.y
      weight = 0.42
    } else if (pointer.moved) {
      u = (pointer.x - rect.left) / rect.width
      v = 1 - (pointer.y - rect.top) / rect.height
      weight = 1
    }

    // A jump this large in one frame is a teleport (control changing hands, the
    // tab coming back, the pointer re-entering the window), not a stroke.
    const jump = Math.hypot((u - this.to.x) * this.aspect, v - this.to.y)
    if (idle !== this.wasIdle || jump > 0.25) this.to.set(u, v)
    this.from.copy(this.to)
    this.to.set(u, v)
    this.wasIdle = idle

    // Dye follows how far the brush travelled this frame; standing still adds none.
    const travelled = Math.hypot((u - this.from.x) * this.aspect, v - this.from.y)
    return { dye: Math.min(0.9, travelled * 12) * weight, force: 22 * weight }
  }

  render(rect, time, dt) {
    const { renderer, pointer, reduced } = this.stage
    this.aspect = rect.width / rect.height
    this.uniforms.uAspect.value = this.aspect
    this.measureSubject(rect)

    // A few pixels of parallax: the portrait leans away from the pointer.
    const targetX = pointer.moved && !reduced ? (pointer.x / this.stage.width) * 2 - 1 : 0
    const targetY = pointer.moved && !reduced ? (pointer.y / this.stage.height) * 2 - 1 : 0
    this.tilt.x += (targetX - this.tilt.x) * 0.05
    this.tilt.y += (targetY - this.tilt.y) * 0.05
    this.uniforms.uShift.value.set(this.tilt.x * 0.006, -this.tilt.y * 0.004)

    const { dye, force } = this.updateBrush(rect)
    this.fluid.resize(rect.width, rect.height)
    this.fluid.update(renderer, {
      from: this.from,
      to: this.to,
      force,
      dye,
      radius: 0.085,
      aspect: this.aspect,
      dt,
    })

    this.uniforms.tTrail.value = this.fluid.texture
    this.uniforms.uTime.value = time
    this.stage.drawToScreen(rect, this.scene, this.camera)
  }
}
