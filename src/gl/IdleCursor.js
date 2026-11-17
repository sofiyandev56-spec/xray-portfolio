import gsap from 'gsap'

/*
  When nobody has moved the pointer for a while, a virtual cursor sweeps the
  portrait so the reveal is discoverable, including on touch screens, which have
  no hover. The rhythm follows landonorris.com: a zig-zag pass down the frame over
  2.5 s, a pause, a pass back up, then a rest before it repeats.

  `point` is in 0..1 of whatever box the caller maps it onto (y up).
*/
export class IdleCursor {
  constructor({ after = 2000, firstAfter = 4200 } = {}) {
    this.after = after
    this.firstAfter = firstAfter
    this.bornAt = performance.now()
    this.active = false
    this.progress = { x: 0, y: 0 }
    this.point = { x: 0.12, y: 0.85 }

    this.timeline = gsap
      .timeline({ paused: true, repeat: -1, repeatDelay: 3 })
      .fromTo(this.progress, { y: 0 }, { y: 1, duration: 2.5, ease: 'none' }, 0)
      .fromTo(this.progress, { x: 0 }, { x: 1, duration: 2.5, ease: 'power1.inOut' }, 0)
      .fromTo(this.progress, { y: 1 }, { y: 0, duration: 2.5, ease: 'none' }, 4)
      .fromTo(this.progress, { x: 1 }, { x: 0, duration: 2.5, ease: 'power1.inOut' }, 4)
  }

  /**
   * @param {{moved: boolean, lastMove: number}} pointer
   * @returns {boolean} whether the virtual cursor is in charge this frame
   */
  update(pointer) {
    const now = performance.now()
    const idle = pointer.moved ? now - pointer.lastMove > this.after : now - this.bornAt > this.firstAfter

    if (idle !== this.active) {
      this.active = idle
      if (idle) this.timeline.seek(0).play()
      else this.timeline.pause()
    }

    if (idle) {
      // Two left-right swings while travelling top to bottom (or back).
      this.point.x = 0.5 - Math.cos(this.progress.x * Math.PI * 4) * 0.38
      this.point.y = 0.5 + Math.cos(this.progress.y * Math.PI) * 0.35
    }
    return idle
  }

  dispose() {
    this.timeline.kill()
  }
}
