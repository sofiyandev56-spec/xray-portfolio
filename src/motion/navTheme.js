import { ScrollTrigger } from 'gsap/ScrollTrigger'

/*
  data-nav-theme="light | dark" on a section: while that section sits under the
  navigation bar, the bar takes that theme (see .nav[data-theme] in base.css).
*/
export function initNavTheme() {
  const nav = document.querySelector('[data-nav]')
  if (!nav) return

  // The line the sections are tested against: the vertical middle of the bar.
  const line = Math.round(nav.offsetHeight / 2)

  document.querySelectorAll('[data-nav-theme]').forEach((section) => {
    ScrollTrigger.create({
      trigger: section,
      start: `top ${line}px`,
      end: `bottom ${line}px`,
      onToggle: (self) => {
        if (self.isActive) nav.dataset.theme = section.dataset.navTheme
      },
    })
  })
}
