"""Build every target from src.html (the single source file).

  python3 tools/build.py
    -> index.html               standalone page for GitHub Pages / any web server (CDN Three.js)
    -> dist/artifact.html       body-only page for publishing as a claude.ai artifact (cars as base64 .txt)
    -> android/app/src/main/assets/   offline copy for the Android app (local Three.js + .car files)
"""
import os, re, shutil, base64, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'src.html')).read()
HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">\n'
        '<meta name="description" content="Nitro Arena - night stadium supercar racing by TERA YAAR SRP">\n')
LIBS = ['build/three.min.js', 'examples/js/shaders/CopyShader.js', 'examples/js/shaders/LuminosityHighPassShader.js',
        'examples/js/postprocessing/EffectComposer.js', 'examples/js/postprocessing/RenderPass.js',
        'examples/js/postprocessing/ShaderPass.js', 'examples/js/postprocessing/UnrealBloomPass.js']

def standalone(s, local_libs):
    if local_libs:
        s = s.replace('https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js', 'lib/three.min.js')
        s = re.sub(r'https://cdn\.jsdelivr\.net/npm/three@0\.128\.0/examples/js/\w+/(\w+\.js)', r'lib/\1', s)
    s = s.replace('<canvas id="c"></canvas>', '</head><body>\n<canvas id="c"></canvas>', 1)
    return HEAD + s + '\n</body></html>\n'

# 1. GitHub Pages
open(os.path.join(ROOT, 'index.html'), 'w').write(standalone(src, False))
# 2. claude.ai artifact (body only, base64 car files)
os.makedirs(os.path.join(ROOT, 'dist', 'cars'), exist_ok=True)
open(os.path.join(ROOT, 'dist', 'artifact.html'), 'w').write(src.replace("<script>\n'use strict';", "<script>\n'use strict';window.CAR_FORMAT='txt';", 1))
for f in glob.glob(os.path.join(ROOT, 'cars', '*.car')):
    open(os.path.join(ROOT, 'dist', 'cars', os.path.basename(f)[:-4] + '.txt'), 'w').write(base64.b64encode(open(f, 'rb').read()).decode())
# 3. Android assets
A = os.path.join(ROOT, 'android', 'app', 'src', 'main', 'assets')
if os.path.isdir(os.path.join(ROOT, 'android')):
    shutil.rmtree(A, ignore_errors=True); os.makedirs(os.path.join(A, 'lib')); shutil.copytree(os.path.join(ROOT, 'cars'), os.path.join(A, 'cars'))
    three = os.environ.get('THREE_SRC', os.path.join(ROOT, 'lib'))
    for l in LIBS:
        p = os.path.join(three, l) if os.path.exists(os.path.join(three, l)) else os.path.join(ROOT, 'lib', os.path.basename(l))
        shutil.copy(p, os.path.join(A, 'lib'))
    open(os.path.join(A, 'index.html'), 'w').write(standalone(src, True))
print('built index.html, dist/artifact.html, android assets')
