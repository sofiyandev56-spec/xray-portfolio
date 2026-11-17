import { SplitText } from 'gsap/SplitText'

/*
  Navigation links, text links (a.link) and anything marked data-roll: on hover
  or keyboard focus, the link's letters roll up one after
  another and an identical copy rolls in from below (the button hover on
  landonorris.com).

  Each letter carries its copy as a text-shadow one line below, and the link
  clips to one line, so the effect is pure CSS transforms (see [data-roll] in
  base.css). JavaScript only splits the letters and numbers them for the stagger.
  SplitText keeps the original text as the link's accessible name.
*/
const SELECTOR = '[data-roll], .nav__links a, a.link'

export function initRoll({ reduced }) {
  if (reduced) return
  document.querySelectorAll(SELECTOR).forEach((el) => {
    const split = SplitText.create(el, { type: 'chars', charsClass: 'roll-char', aria: 'auto' })
    split.chars.forEach((char, i) => char.style.setProperty('--i', i))
    el.classList.add('is-rolling')
  })
}
