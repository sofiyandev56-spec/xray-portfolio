# x-ray sources

`tools/xray/build.py` reads these files. The images are third-party, so they are
not committed (see `.gitignore`); keep your own copies to rebuild the x-ray.

| File | What it is | Where it came from |
|---|---|---|
| `skull.jpg` | Frontal skull illustration, 523 x 790 | Supplied by the owner; source and licence not recorded |
| `skull-mask.png` | Cut-out mask of `skull.jpg` | Generated on-device with Apple's Vision framework |
| `macbook-air-teardown.jpg` | MacBook Air with the bottom case removed, 2000 x 1500 | Supplied by the owner; looks like an iFixit teardown photo (CC BY-NC-SA) |
| `m4-chip.jpg` | Apple M4 chip artwork, 337 x 337 | Apple marketing artwork |
| `photo-keypoints.json` | Face and pose landmarks of the original photo | Generated with Apple's Vision framework (committed) |
| `photo-crop.json` | Where `public/hero/portrait.webp` was cut from the original photo | Generated (committed) |

The skeleton below the skull is drawn in code by `build.py`; a frontal anatomy
reference was used for proportions only.
