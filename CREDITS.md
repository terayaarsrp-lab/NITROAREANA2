# Credits

**Nitro Arena** is created by **TERA YAAR SRP**.

## 3D car models

The cars are real models from [Sketchfab](https://sketchfab.com), converted for the game with `tools/convert.py`
(simplified, hidden parts removed, textures resized, recoloured with team liveries). They are used under
Creative Commons licences, which require the credit below.

| In game | File | Original model | Author | Licence |
|---|---|---|---|---|
| Blade GT3 | `cars/blade.car` | [2015 McLaren 650S GT3](https://sketchfab.com/3d-models/2015-mclaren-650s-gt3-e3e3452c86d74f6aa74a1ba60cfdf19b) | Dave Love SketchFab | CC-BY-4.0 |
| Classic Ray 64 | `cars/classicray.car` | [1964 Chevrolet Corvette Sting Ray](https://sketchfab.com/3d-models/1964-chevrolet-corvette-sting-ray-80f110c7094c4c89ad3f8029fa280ca1) | VTX | CC-BY-NC-SA-4.0 (non-commercial) |
| Jewel 67 | `cars/jewel.car` | [1967 Chevy Camaro SS Hidden Jewel](https://sketchfab.com/3d-models/1967-chevy-camaro-ss-hidden-jewel-2cd3999a0f0444e2a57b5f1aad92e890) | Ddiaz Design | CC-BY-NC-SA-4.0 (non-commercial) |
| Legend GT1 | `cars/legend.car` | [1996 Porsche 911 GT1](https://sketchfab.com/3d-models/1996-porsche-911-gt1-9930af5fcd30467a84247d15d75896a5) | Dave Love SketchFab | CC-BY-4.0 |
| Liberty SS | `cars/liberty.car` | [2016 chevrolet camaro ss independence edition](https://sketchfab.com/3d-models/2016-chevrolet-camaro-ss-independence-edition-f8a3895270c741a4a58e0409c27570fa) | amogusstrikesback2 | CC-BY-4.0 |
| Muscle RS | `cars/musclers.car` | [2010 Chevrolet Camaro RS GMOD](https://sketchfab.com/3d-models/2010-chevrolet-camaro-rs-gmod-62695f4c215343b9875d70f0eaed9e56) | Pipogame | CC-BY-4.0 |
| Oval Beast | `cars/ovalbeast.car` | [2021 NASCAR ForeverLawn Chevrolet Camaro SS](https://sketchfab.com/3d-models/2021-nascar-foreverlawn-chevrolet-camaro-ss-a2f629371f6d427f8754102097c6f0b1) | Ddiaz Design | CC-BY-4.0 |
| Razor GT3 | `cars/razor.car` | [2020 McLaren 720S GT3](https://sketchfab.com/3d-models/2020-mclaren-720s-gt3-c368cc22dcb8480e9e942e57fb63c635) | Dave Love SketchFab | CC-BY-4.0 |
| Rexy GT3 R | `cars/rexy.car` | [Porsche 992 GT3 R "Rexy Skeleton"](https://sketchfab.com/3d-models/porsche-992-gt3-r-rexy-skeleton-75bf8a8871c146048e5b42154e56cc8b) | VTX | CC-BY-NC-SA-4.0 (non-commercial) |
| Roxy GT3 R | `cars/roxy.car` | [Porsche 992 GT3 R "Roxy"](https://sketchfab.com/3d-models/porsche-992-gt3-r-roxy-7c86ab48c79d4310b5618da1f74b57d3) | VTX | CC-BY-NC-SA-4.0 (non-commercial) |
| Sting C7 | `cars/sting.car` | [chevrolet corvette c7 stingray](https://sketchfab.com/3d-models/chevrolet-corvette-c7-stingray-179ca9f5787946dfb539fc6eed8bb626) | amogusstrikesback2 | CC-BY-4.0 |
| Storm GT3 R | `cars/storm.car` | [2024 Porsche 992 GT3 R](https://sketchfab.com/3d-models/2024-porsche-992-gt3-r-b76c9b2ae2d548c3869426eac4ab8a19) | Dave Love SketchFab | CC-BY-4.0 |
| Trail RS | `cars/trail.car` | [2022 Chevrolet Tracker RS 335T](https://sketchfab.com/3d-models/2022-chevrolet-tracker-rs-335t-43e7378889b34e9cabf23e6f386d4b87) | Ddiaz Design | CC-BY-NC-SA-4.0 (non-commercial) |
| Classic Turbo 75 | `cars/turbo75.car` | [1975 Porsche 911 (930) Turbo](https://sketchfab.com/3d-models/1975-porsche-911-930-turbo-86b165439ff4483a981629ffc10d4e10) | VTX | CC-BY-NC-SA-4.0 (non-commercial) |
| Venom C6 | `cars/venomc6.car` | [2012 Chevrolet Corvette C6 ZR1](https://sketchfab.com/3d-models/2012-chevrolet-corvette-c6-zr1-149cab111ae341b890f2250121741b75) | OUTPISTON | CC-BY-NC-SA-4.0 (non-commercial) |
| Venom ZR | `cars/venomzr.car` | [chevrolet corvette zr1 (c7)](https://sketchfab.com/3d-models/chevrolet-corvette-zr1-c7-c478bcc81ee745eb838e787911568294) | amogusstrikesback2 | CC-BY-4.0 |

**Important:** the models marked *non-commercial* (CC BY-NC-SA 4.0) may only be used in a free, non-commercial
game, and changed versions must be shared under the same licence. If you ever want to sell the game, add ads
or in-app purchases, remove those cars first (delete the file in `cars/` and its line in `CARS` in `src.html`).

The models show real car designs and some liveries include real brand logos. Car makers own those designs and
trademarks; Nitro Arena is not affiliated with or endorsed by any of them. The in-game names are fictional.

## Libraries

- [three.js](https://threejs.org) r128 (MIT licence, see `lib/THREE-LICENSE.txt`), with its EffectComposer,
  RenderPass, ShaderPass, CopyShader, LuminosityHighPassShader and UnrealBloomPass examples.
- Fonts: Big Shoulders Display and Chakra Petch from Google Fonts (SIL Open Font Licence).

## Sound and music

All music, engine sounds and effects are synthesised live with the Web Audio API in `src.html`. There are no
audio files.
