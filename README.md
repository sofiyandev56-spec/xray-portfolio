# Sofiyan Shaikh — portfolio

A one-page portfolio. It opens as a blueprint while the signature is written
across it stroke by stroke, then develops into a photo. Moving the cursor over the
photo stirs a small fluid simulation that wipes it back to an x-ray: the skull and
skeleton under the face, the inside of the MacBook and its M4 chip under the lid.
Leave the cursor alone and a virtual one sweeps the photo for you.

Built with Vite, Three.js, GSAP and Lenis. No framework.

## Run it

```bash
npm install
```

```bash
npm run dev
```

```bash
npm run build
```

`npm run build` writes a static site to `dist/` that any static host (Vercel,
Netlify, GitHub Pages) can serve.

## What is where

```
index.html                     all words, links and projects
public/hero/portrait.webp      the cut-out photo (843 x 818)
public/hero/xray.webp          what the cursor reveals; built by tools/xray/build.py
public/hero/signature.png      the signature's ink as transparency
public/certificates/           certificate scans shown in the Work gallery
public/files/                  résumé and CV PDFs
public/og-image.jpg            the link preview; built by tools/social/build.py
src/main.js                    boot order: WebGL, fonts, scroll, behaviours, intro
src/styles/tokens.css          colours, fonts, the ease, the fluid type scale
src/styles/sections.css        hero, about, tools band, work, record, contact, layouts
src/gl/Stage.js                one WebGL canvas; maps [data-gl] elements to scenes
src/gl/scenes/HeroScene.js     photo, x-ray, and the mask between them
src/gl/Fluid.js                the stable-fluids simulation the cursor stirs
src/gl/IdleCursor.js           the sweep that runs when nobody moves the pointer
src/gl/scenes/ContoursScene.js the contour lines behind the contact section
src/motion/intro.js            the load sequence, timed to the signature
src/motion/signature.js        the signature, written stroke by stroke
src/motion/roll.js             the letter-roll hover on links
src/motion/ticker.js           the tools band that answers the scroll
src/motion/horizontal.js       the sideways Work gallery and its depth
src/data/signature-strokes.json  the pen strokes; built by tools/signature/vectorize.py
tools/                         the scripts that build the generated assets
```

## How the motion works

The behaviour was modelled on a study of landonorris.com's code, then built from
scratch for this design.

| | How it works here |
|---|---|
| Smooth scroll | Lenis at lerp 0.1, touch smoothed too (`syncTouch`), on GSAP's ticker with ScrollTrigger and WebGL |
| Cursor | A stable-fluids simulation (vorticity, pressure solve, advection) at a fixed 60 steps a second; the cursor pushes the flow and drops "dye", and the dye is the reveal mask |
| Idle | After two quiet seconds a virtual cursor zig-zags down the photo in 2.5 s, pauses, sweeps back, rests 3 s, repeats |
| Signature | Centre lines traced from the real ink and ordered like handwriting (letters, dots, then the flourishes); invisible strokes along them reveal the ink. The intro writes it on a timer; the footer writes it with the scroll and rewinds it on the way back |
| Links | Letters roll up one after another on hover and keyboard focus |
| Tools band | Drifts sideways, speeds up and leans with scroll speed, reverses on scroll up |
| Gallery | Sideways on desktop via CSS sticky; each drawing drifts against the travel for depth |

All of it stands down for `prefers-reduced-motion`: no smooth scroll, no intro,
no idle sweep, no roll, and the gallery stacks.

## Editing content

- **Projects:** each is an `<article class="sheet">` in the Work section of
  `index.html`. Copy one to add another.
- **Certificates:** put the scan in `public/certificates/` and copy the
  `sheet--certificate` article.
- **Résumé and CV:** replace the PDFs in `public/files/`, keeping the file names.
- **Tools band:** edit the list in the `ticker` section of `index.html`.

## Generated assets

```bash
python3 tools/xray/build.py --preview
```

```bash
python3 tools/signature/vectorize.py --preview
```

```bash
python3 tools/social/build.py
```

They need Pillow and NumPy. The x-ray needs the source images described in
`tools/xray/sources/README.md`, which are not in the repo. If you change the
photo, re-measure the positions at the top of `tools/xray/build.py`, and keep
`portrait.webp` and `xray.webp` the same aspect ratio.

## Before you deploy

- **Image credits.** The x-ray is built from three images that were not made for
  this site: a skull illustration whose source is not recorded, a MacBook Air
  teardown photo that looks like iFixit's (CC BY-NC-SA, which asks for credit and
  non-commercial use), and Apple's M4 chip artwork. Add a credits line once the
  sources are known, or swap in images you have the rights to.
- **The teardown is not an M4.** The photo shows a MacBook Air with a fan, the
  Intel-era model; Apple silicon Airs, including the M4, are fanless.
- **The résumé PDF includes a phone number** and still lists the agilescitech.in
  rebuild, which is no longer claimed on the site.
- **Link previews:** make `og:image` in `index.html` an absolute URL once the site
  has a domain; some services ignore relative ones.

## Good to know

- Text sizes follow the viewport between set widths (`tokens.css`), so the layout
  keeps its proportions; small text has pixel minimums.
- Sections must not create a stacking context (no `z-index`, `transform` or
  `opacity` on the section itself) or their text falls behind the WebGL canvas.
- Without WebGL, or if the GPU drops the context, the page falls back to the plain
  photo and flat backgrounds.
- `window.__portfolio` exposes the stage, Lenis, GSAP and the signature timeline
  in development only.
