import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'

/*
  data-split="lines": the element's lines rise out of a mask the first time it
  scrolls into view. SplitText re-splits on resize or late font loads (autoSplit)
  and keeps the original sentence available to screen readers.

  Reserve this for a few headings. On every block of text it stops meaning anything.
*/
export function initSplit({ reduced }) {
  const targets = document.querySelectorAll('[data-split]')

  if (reduced) {
    gsap.set(targets, { visibility: 'visible' })
    return
  }

  targets.forEach((el) => {
    SplitText.create(el, {
      type: 'lines',
      mask: 'lines',
      linesClass: 'line',
      autoSplit: true,
      onSplit(self) {
        gsap.set(el, { visibility: 'visible' })
        // Returning the tween lets SplitText carry its progress across a re-split.
        return gsap.from(self.lines, {
          yPercent: 130, // past the mask (~113% of a line) and the capitals' overshoot: fully hidden
          duration: 1,
          ease: 'house',
          stagger: 0.09,
          scrollTrigger: { trigger: el, start: 'top 85%', once: true },
        })
      },
    })
  })
}
