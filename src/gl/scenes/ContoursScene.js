import * as THREE from 'three'
import { snoise, lines, fullscreenVert } from '../noise.glsl.js'

/*
  The smallest useful scene: one fragment shader on a full-rectangle quad.
  It draws drifting contour lines on blueprint blue, and the lines bulge into
  rings around the pointer. Use it as the template for new scenes.
*/
const fragmentShader = /* glsl */ `
uniform float uTime;
uniform float uAspect;
uniform vec2 uPointer;
uniform float uPointerStrength;
uniform vec3 uBlue;
uniform vec3 uBlueLine;
varying vec2 vUv;

${snoise}
${lines}

void main() {
  vec2 p = vec2(vUv.x * uAspect, vUv.y);

  vec2 d = p - vec2(uPointer.x * uAspect, uPointer.y);
  float bump = exp(-dot(d, d) / 0.045) * uPointerStrength;

  float field = snoise(vec3(p * 1.2, uTime * 0.04)) * 0.5 + 0.5 + bump * 0.2;
  vec3 color = mix(uBlue, uBlueLine, isoLines(field, 10.0) * 0.32);

  gl_FragColor = vec4(color, 1.0);
  #include <colorspace_fragment>
}
`

export class ContoursScene {
  name = 'contours'

  constructor(stage, el) {
    this.stage = stage
    this.el = el

    this.uniforms = {
      uTime: { value: 0 },
      uAspect: { value: 1 },
      uPointer: { value: new THREE.Vector2(0.5, 0.5) },
      uPointerStrength: { value: 0 },
      uBlue: { value: stage.colors.blue },
      uBlueLine: { value: stage.colors.line },
    }

    this.scene = new THREE.Scene()
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    this.scene.add(
      new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        new THREE.ShaderMaterial({
          uniforms: this.uniforms,
          vertexShader: fullscreenVert,
          fragmentShader,
          depthTest: false,
          depthWrite: false,
        }),
      ),
    )
  }

  render(rect, time) {
    const { pointer, reduced } = this.stage
    const u = this.uniforms
    u.uAspect.value = rect.width / rect.height
    u.uTime.value = reduced ? 0 : time

    // Ease the bulge toward the pointer while it is over this element.
    const x = (pointer.x - rect.left) / rect.width
    const y = 1 - (pointer.y - rect.top) / rect.height
    const over = pointer.moved && x >= 0 && x <= 1 && y >= 0 && y <= 1
    if (over) {
      u.uPointer.value.x += (x - u.uPointer.value.x) * 0.08
      u.uPointer.value.y += (y - u.uPointer.value.y) * 0.08
    }
    u.uPointerStrength.value += ((over ? 1 : 0) - u.uPointerStrength.value) * 0.05

    this.stage.drawToScreen(rect, this.scene, this.camera)
  }
}
