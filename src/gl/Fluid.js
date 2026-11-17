import * as THREE from 'three'
import { fullscreenVert } from './noise.glsl.js'

/*
  A small stable-fluids simulation (Stam 1999) that turns cursor movement into a
  swirling mask.

  Two fields live on the GPU:
    velocity  how the "fluid" is moving, in grid cells per second (xy)
    dye       how much of the reveal is at each point (x)

  Every frame the pointer pushes velocity and drops dye along the segment it just
  travelled. Then, at a fixed 60 steps per second, the solver:
    adds vorticity (keeps small eddies curling instead of smearing out),
    makes the flow incompressible (divergence -> pressure -> subtract gradient),
    and carries both fields along the flow (semi-Lagrangian advection),
  fading each a little so the reveal settles when the cursor stops.

  `texture` is the dye; HeroScene thresholds it into a crisp-edged mask.
*/

const STEP = 1 / 60
const MAX_PUSH = 420 // cells per second

const splatFrag = /* glsl */ `
uniform sampler2D tTarget;
uniform vec2 uFrom;
uniform vec2 uTo;
uniform vec3 uValue;
uniform float uRadius;
uniform float uAspect;
uniform float uMax;
varying vec2 vUv;

void main() {
  // Distance from this cell to the segment the pointer travelled, in square units.
  vec2 pa = vUv - uFrom;
  vec2 ba = uTo - uFrom;
  pa.x *= uAspect;
  ba.x *= uAspect;
  float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
  float d = length(pa - ba * h);
  float falloff = exp(-(d * d) / (uRadius * uRadius));

  vec3 value = texture2D(tTarget, vUv).xyz + uValue * falloff;
  gl_FragColor = vec4(clamp(value, -uMax, uMax), 1.0);
}
`

const curlFrag = /* glsl */ `
uniform sampler2D tVelocity;
uniform vec2 uTexel;
varying vec2 vUv;

void main() {
  float L = texture2D(tVelocity, vUv - vec2(uTexel.x, 0.0)).y;
  float R = texture2D(tVelocity, vUv + vec2(uTexel.x, 0.0)).y;
  float T = texture2D(tVelocity, vUv + vec2(0.0, uTexel.y)).x;
  float B = texture2D(tVelocity, vUv - vec2(0.0, uTexel.y)).x;
  gl_FragColor = vec4(0.5 * (R - L - T + B), 0.0, 0.0, 1.0);
}
`

const vorticityFrag = /* glsl */ `
uniform sampler2D tVelocity;
uniform sampler2D tCurl;
uniform vec2 uTexel;
uniform float uCurl;
uniform float uDt;
varying vec2 vUv;

void main() {
  float L = texture2D(tCurl, vUv - vec2(uTexel.x, 0.0)).x;
  float R = texture2D(tCurl, vUv + vec2(uTexel.x, 0.0)).x;
  float T = texture2D(tCurl, vUv + vec2(0.0, uTexel.y)).x;
  float B = texture2D(tCurl, vUv - vec2(0.0, uTexel.y)).x;
  float C = texture2D(tCurl, vUv).x;

  vec2 force = 0.5 * vec2(abs(T) - abs(B), abs(R) - abs(L));
  force /= length(force) + 1e-4;
  force *= uCurl * C;
  force.y *= -1.0;

  vec2 velocity = texture2D(tVelocity, vUv).xy + force * uDt;
  gl_FragColor = vec4(clamp(velocity, -1000.0, 1000.0), 0.0, 1.0);
}
`

const divergenceFrag = /* glsl */ `
uniform sampler2D tVelocity;
uniform vec2 uTexel;
varying vec2 vUv;

void main() {
  vec2 C = texture2D(tVelocity, vUv).xy;
  float L = texture2D(tVelocity, vUv - vec2(uTexel.x, 0.0)).x;
  float R = texture2D(tVelocity, vUv + vec2(uTexel.x, 0.0)).x;
  float T = texture2D(tVelocity, vUv + vec2(0.0, uTexel.y)).y;
  float B = texture2D(tVelocity, vUv - vec2(0.0, uTexel.y)).y;

  // Solid walls: flow at the edge of the box reflects instead of leaking out.
  if (vUv.x - uTexel.x < 0.0) L = -C.x;
  if (vUv.x + uTexel.x > 1.0) R = -C.x;
  if (vUv.y + uTexel.y > 1.0) T = -C.y;
  if (vUv.y - uTexel.y < 0.0) B = -C.y;

  gl_FragColor = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);
}
`

const scaleFrag = /* glsl */ `
uniform sampler2D tSource;
uniform float uScale;
varying vec2 vUv;

void main() {
  gl_FragColor = texture2D(tSource, vUv) * uScale;
}
`

const pressureFrag = /* glsl */ `
uniform sampler2D tPressure;
uniform sampler2D tDivergence;
uniform vec2 uTexel;
varying vec2 vUv;

void main() {
  float L = texture2D(tPressure, vUv - vec2(uTexel.x, 0.0)).x;
  float R = texture2D(tPressure, vUv + vec2(uTexel.x, 0.0)).x;
  float T = texture2D(tPressure, vUv + vec2(0.0, uTexel.y)).x;
  float B = texture2D(tPressure, vUv - vec2(0.0, uTexel.y)).x;
  float divergence = texture2D(tDivergence, vUv).x;
  gl_FragColor = vec4((L + R + B + T - divergence) * 0.25, 0.0, 0.0, 1.0);
}
`

const gradientFrag = /* glsl */ `
uniform sampler2D tPressure;
uniform sampler2D tVelocity;
uniform vec2 uTexel;
varying vec2 vUv;

void main() {
  float L = texture2D(tPressure, vUv - vec2(uTexel.x, 0.0)).x;
  float R = texture2D(tPressure, vUv + vec2(uTexel.x, 0.0)).x;
  float T = texture2D(tPressure, vUv + vec2(0.0, uTexel.y)).x;
  float B = texture2D(tPressure, vUv - vec2(0.0, uTexel.y)).x;
  vec2 velocity = texture2D(tVelocity, vUv).xy - vec2(R - L, T - B);
  gl_FragColor = vec4(velocity, 0.0, 1.0);
}
`

const advectFrag = /* glsl */ `
uniform sampler2D tVelocity;
uniform sampler2D tSource;
uniform vec2 uTexel;
uniform float uDt;
uniform float uDissipation;
uniform float uFloor;
varying vec2 vUv;

void main() {
  // Look back along the flow to find what arrives here this step.
  vec2 from = vUv - uDt * texture2D(tVelocity, vUv).xy * uTexel;
  vec4 value = texture2D(tSource, from) * uDissipation;
  // Dye only: shave a little off so faint traces reach exactly zero.
  if (uFloor > 0.0) value = max(value - uFloor, 0.0);
  gl_FragColor = value;
}
`

function makeTarget(w, h) {
  return new THREE.WebGLRenderTarget(w, h, {
    type: THREE.HalfFloatType,
    format: THREE.RGBAFormat,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    wrapS: THREE.ClampToEdgeWrapping,
    wrapT: THREE.ClampToEdgeWrapping,
    depthBuffer: false,
  })
}

class PingPong {
  constructor(w, h) {
    this.read = makeTarget(w, h)
    this.write = makeTarget(w, h)
  }

  swap() {
    const t = this.read
    this.read = this.write
    this.write = t
  }

  setSize(w, h) {
    this.read.setSize(w, h)
    this.write.setSize(w, h)
  }

  dispose() {
    this.read.dispose()
    this.write.dispose()
  }
}

export class Fluid {
  /**
   * @param {object} options
   * @param {number} options.cellsPerPixel  simulation cells per CSS pixel of the element
   * @param {number} options.dyeScale       dye resolution relative to the simulation
   * @param {number} options.curl           vorticity strength
   * @param {number} options.iterations     pressure solver iterations
   * @param {number} options.velocityFade   velocity kept per step (0..1)
   * @param {number} options.dyeFade        dye kept per step (0..1)
   */
  constructor({
    cellsPerPixel = 0.12,
    dyeScale = 2,
    curl = 18,
    iterations = 16,
    velocityFade = 0.965,
    dyeFade = 0.968,
  } = {}) {
    this.options = { cellsPerPixel, dyeScale, curl, iterations, velocityFade, dyeFade }
    this.simSize = new THREE.Vector2(0, 0)
    this.dyeSize = new THREE.Vector2(0, 0)
    this.texel = new THREE.Vector2(0.5, 0.5)
    this.accumulator = 0
    this.push = new THREE.Vector3()
    this.ink = new THREE.Vector3()

    this.velocity = new PingPong(2, 2)
    this.dye = new PingPong(2, 2)
    this.pressure = new PingPong(2, 2)
    this.divergence = makeTarget(2, 2)
    this.curlTarget = makeTarget(2, 2)

    const material = (fragmentShader, uniforms) =>
      new THREE.ShaderMaterial({
        vertexShader: fullscreenVert,
        fragmentShader,
        uniforms,
        depthTest: false,
        depthWrite: false,
      })
    const texel = { value: this.texel }

    this.materials = {
      splat: material(splatFrag, {
        tTarget: { value: null },
        uFrom: { value: new THREE.Vector2() },
        uTo: { value: new THREE.Vector2() },
        uValue: { value: new THREE.Vector3() },
        uRadius: { value: 0.1 },
        uAspect: { value: 1 },
        uMax: { value: 1000 },
      }),
      curl: material(curlFrag, { tVelocity: { value: null }, uTexel: texel }),
      vorticity: material(vorticityFrag, {
        tVelocity: { value: null },
        tCurl: { value: null },
        uTexel: texel,
        uCurl: { value: curl },
        uDt: { value: STEP },
      }),
      divergence: material(divergenceFrag, { tVelocity: { value: null }, uTexel: texel }),
      scale: material(scaleFrag, { tSource: { value: null }, uScale: { value: 0.8 } }),
      pressure: material(pressureFrag, {
        tPressure: { value: null },
        tDivergence: { value: null },
        uTexel: texel,
      }),
      gradient: material(gradientFrag, {
        tPressure: { value: null },
        tVelocity: { value: null },
        uTexel: texel,
      }),
      advect: material(advectFrag, {
        tVelocity: { value: null },
        tSource: { value: null },
        uTexel: texel,
        uDt: { value: STEP },
        uDissipation: { value: 1 },
        uFloor: { value: 0 },
      }),
    }

    this.scene = new THREE.Scene()
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.materials.splat)
    this.scene.add(this.quad)
  }

  /** The reveal mask (red channel), as of the last update. */
  get texture() {
    return this.dye.read.texture
  }

  /** Match the grid to the element's size, so cells stay square on screen. */
  resize(width, height) {
    const { cellsPerPixel, dyeScale } = this.options
    const w = Math.max(32, Math.round(width * cellsPerPixel))
    const h = Math.max(32, Math.round(height * cellsPerPixel))
    if (w === this.simSize.x && h === this.simSize.y) return
    this.simSize.set(w, h)
    this.dyeSize.set(Math.round(w * dyeScale), Math.round(h * dyeScale))
    this.texel.set(1 / w, 1 / h)
    this.velocity.setSize(w, h)
    this.pressure.setSize(w, h)
    this.divergence.setSize(w, h)
    this.curlTarget.setSize(w, h)
    this.dye.setSize(this.dyeSize.x, this.dyeSize.y)
  }

  pass(renderer, material, target) {
    this.quad.material = material
    renderer.setRenderTarget(target)
    renderer.render(this.scene, this.camera)
  }

  splat(renderer, field, from, to, value, radius, aspect, max) {
    const u = this.materials.splat.uniforms
    u.tTarget.value = field.read.texture
    u.uFrom.value.copy(from)
    u.uTo.value.copy(to)
    u.uValue.value.copy(value)
    u.uRadius.value = radius
    u.uAspect.value = aspect
    u.uMax.value = max
    this.pass(renderer, this.materials.splat, field.write)
    field.swap()
  }

  step(renderer) {
    const m = this.materials
    const { iterations, velocityFade, dyeFade } = this.options

    m.curl.uniforms.tVelocity.value = this.velocity.read.texture
    this.pass(renderer, m.curl, this.curlTarget)

    m.vorticity.uniforms.tVelocity.value = this.velocity.read.texture
    m.vorticity.uniforms.tCurl.value = this.curlTarget.texture
    this.pass(renderer, m.vorticity, this.velocity.write)
    this.velocity.swap()

    m.divergence.uniforms.tVelocity.value = this.velocity.read.texture
    this.pass(renderer, m.divergence, this.divergence)

    // Start the solve from most of last step's pressure; it converges faster.
    m.scale.uniforms.tSource.value = this.pressure.read.texture
    this.pass(renderer, m.scale, this.pressure.write)
    this.pressure.swap()

    m.pressure.uniforms.tDivergence.value = this.divergence.texture
    for (let i = 0; i < iterations; i++) {
      m.pressure.uniforms.tPressure.value = this.pressure.read.texture
      this.pass(renderer, m.pressure, this.pressure.write)
      this.pressure.swap()
    }

    m.gradient.uniforms.tPressure.value = this.pressure.read.texture
    m.gradient.uniforms.tVelocity.value = this.velocity.read.texture
    this.pass(renderer, m.gradient, this.velocity.write)
    this.velocity.swap()

    const a = m.advect.uniforms
    a.tVelocity.value = this.velocity.read.texture
    a.tSource.value = this.velocity.read.texture
    a.uDissipation.value = velocityFade
    a.uFloor.value = 0
    this.pass(renderer, m.advect, this.velocity.write)
    this.velocity.swap()

    a.tVelocity.value = this.velocity.read.texture
    a.tSource.value = this.dye.read.texture
    a.uDissipation.value = dyeFade
    a.uFloor.value = 0.0012
    this.pass(renderer, m.advect, this.dye.write)
    this.dye.swap()
  }

  /**
   * @param {THREE.WebGLRenderer} renderer
   * @param {object} frame
   * @param {THREE.Vector2} frame.from   pointer last frame, in the element's uv (y up)
   * @param {THREE.Vector2} frame.to     pointer this frame
   * @param {number} frame.force         how hard the movement pushes the fluid
   * @param {number} frame.dye           how much reveal to drop along the way (0..1)
   * @param {number} frame.radius        brush radius, as a fraction of the element's height
   * @param {number} frame.aspect        element width / height
   * @param {number} frame.dt            seconds since the last frame
   */
  update(renderer, { from, to, force, dye, radius, aspect, dt }) {
    const dx = to.x - from.x
    const dy = to.y - from.y
    if (force > 0 && (dx !== 0 || dy !== 0)) {
      // The pointer's movement this frame, as cells per second. Capped, so one
      // long frame (a slow device, a tab coming back) can't blow the flow up.
      this.push.set(dx * this.simSize.x, dy * this.simSize.y, 0).multiplyScalar(force).clampLength(0, MAX_PUSH)
      this.splat(renderer, this.velocity, from, to, this.push, radius, aspect, 1000)
    }
    if (dye > 0) {
      this.ink.set(dye, 0, 0)
      this.splat(renderer, this.dye, from, to, this.ink, radius, aspect, 1.4)
    }

    // Fixed steps keep the motion the same on 60 Hz and 120 Hz screens.
    this.accumulator = Math.min(this.accumulator + dt, STEP * 4)
    let steps = 0
    while (this.accumulator >= STEP && steps < 3) {
      this.step(renderer)
      this.accumulator -= STEP
      steps++
    }
  }

  dispose() {
    this.velocity.dispose()
    this.dye.dispose()
    this.pressure.dispose()
    this.divergence.dispose()
    this.curlTarget.dispose()
    Object.values(this.materials).forEach((m) => m.dispose())
    this.quad.geometry.dispose()
  }
}
