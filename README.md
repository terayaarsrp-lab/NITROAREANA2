<p align="center"><img src="docs/icon.png" width="120" alt="Nitro Arena icon"></p>

<h1 align="center">Nitro Arena</h1>
<p align="center"><b>Night stadium supercar racing · created by TERA YAAR SRP</b></p>

![Racing in the Storm Stadium](docs/race.jpg)

Nitro Arena is a 3D racing game that runs in the browser and on Android. 25 cars race on twisty tracks
inside floodlit night stadiums, with cheering crowds, cheerleaders, nitro, coins and a full garage.

## Features

- **16 real supercars** (GT3 race cars, Corvettes, Camaros, a classic 911 and more), each with its own handling
  and engine sound. Rival cars wear team colours and sponsor names; your car carries your racer tag.
- **6 night stadiums**: Neon Arena, Golden Bowl, Moonlight Oval, Storm Stadium (rain and lightning),
  Fog Night Circuit and Inferno Night GP (fireworks). Finish in the top 3 to unlock the next one.
- **Online multiplayer** on claude.ai: friends sign in with their Claude accounts, join with a 5-letter race code
  and race live, with AI cars filling the grid. Stats and a friends leaderboard are saved to each account.
- **Garage**: 5 upgrades, 6 paint jobs, rim colours and neon underglow, bought with coins from races.
- **Realistic driving**: grip and downforce, braking zones, drifting with tyre smoke and skid marks,
  damage, driving assist (Easy, Normal, Pro), four cameras.
- **Sound**: phonk race music and synthwave menu music, engines, turbo, backfires and crowd, all generated live.
- Menus: splash, main menu, stadium select, garage, settings (music, sound, volume, graphics, camera,
  assist, controls), how to play, leaderboard, credits, pause and results.

![The 16 cars](docs/cars.jpg)

## Play

| Where | How |
|---|---|
| Browser | Open `index.html` through any web server, or the GitHub Pages link of this repo. |
| Android | Install the APK from the latest Release or from the **Build Android APK** workflow artifacts. |
| claude.ai | The claude.ai version adds online multiplayer and account sync. |

Controls: **W/↑** accelerate, **S/↓** brake, **A D / ← →** steer, **Shift** nitro, **Space** handbrake,
**C** camera, **P/Esc** pause. On phones, drag your left thumb to steer (or pick Buttons or Tilt steering in
Settings) and use the GAS, BRK and NOS buttons on the right. Auto accelerate and steering sensitivity are in Settings.
The game renders at the phone's full sharpness with anti-aliasing and lowers the resolution a little only if the
frame rate drops.

> Opening `index.html` straight from your disk (`file://`) blocks the car files in most browsers.
> Run a tiny server instead: `python3 -m http.server` in this folder, then open http://localhost:8000.

## Publish on GitHub

1. Create a new repository on GitHub and upload everything in this folder (or `git push` it).
2. **Website:** Settings → Pages → Source: **GitHub Actions**. The `Deploy to GitHub Pages` workflow publishes
   the game at `https://<your-name>.github.io/<repo>/`.
3. **Android app:** the `Build Android APK` workflow runs on every push. Open the run in the Actions tab and
   download `NitroArena-apk`. Attach it to a Release so players can download it.

## Project layout

```
src.html            the whole game (HTML, CSS, JavaScript) - edit this file
index.html          generated from src.html for the web (tools/build.py)
cars/*.car          the 16 optimised car models (see CREDITS.md)
lib/                three.js r128, bundled into the Android app
android/            Android Studio project (WebView app); assets are filled in by tools/build.py
tools/build.py      builds index.html, the claude.ai page and the Android assets from src.html
tools/convert.py    turns a .glb car model into a .car file
tools/fixwheels.py  repairs wheel pivots so tyres spin on their axle and the car sits on the ground
tools/carinfo.js    prints the wheel geometry of .car files (node tools/carinfo.js cars/*.car)
.github/workflows/  GitHub Pages and APK builds
```

After editing `src.html`, run `python3 tools/build.py` and commit the result.

## Add your own car

1. Download a car as `.glb` (Sketchfab "game-ready", ideally under 50 MB, with separate wheels). Check that its
   licence allows use in a game and credit the author.
2. Add it to a list like `tools/cars.example.json`:
   `{"id": "mycar", "name": "My Car", "src": "models/my_car.glb"}`
3. Convert and repair:
   ```
   pip install numpy pillow
   python3 tools/convert.py tools/cars.example.json cars/ "" mycar
   python3 tools/fixwheels.py cars/mycar.car
   ```
4. Add `{id:'mycar',name:'My Car',cls:'sport'}` to the `CARS` list in `src.html`
   (`cls` is one of `gt3`, `sport`, `muscle`, `classic`, `suv`), run `python3 tools/build.py`, and add the credit
   to `CREDITS.md`.

If a car faces backwards add `"flip": true`; if it is the wrong size add `"scale": 0.9` (or similar).

## Build the APK yourself

Install Android Studio (or JDK 17 + Gradle 8.7 + Android SDK 34), then:

```
python3 tools/build.py
gradle -p android assembleDebug
```

The APK is in `android/app/build/outputs/apk/debug/`.

## Credits and licence

Game created by **TERA YAAR SRP**. Code under the MIT licence (see `LICENSE`).
The car models belong to their authors and keep their own Creative Commons licences; several are
**non-commercial only**. Read `CREDITS.md` before using this game commercially.
