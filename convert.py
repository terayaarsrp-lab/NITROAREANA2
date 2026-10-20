"""Convert heavy .glb car models (for example from Sketchfab) into small game-ready .car files.

Usage:
  python3 tools/convert.py tools/cars.json cars/ [preview_dir] [only_id ...]

cars.json is a list of {"id", "name", "src"} plus optional "flip" (true/false, front/back),
"scale" (multiplier) and "paint" (exact material name of the body paint).

Pipeline: load glTF -> flatten the scene (skins included) -> drop junk by name and baked ground shadows
-> remove stray far-away parts -> orient (length on Z, front +Z, wheels on y=0) -> visibility cull
(triangles nobody can see from outside the car are removed) -> find the 4 wheels -> vertex-cluster
decimation into a high and a low detail level -> resize textures -> pack a quantised binary.
Run tools/fixwheels.py on the output afterwards to repair wheel pivots on unusual models.
"""
import json, struct, sys, io, math, os, re
import numpy as np
from PIL import Image

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
NMAX = {5120: 127., 5121: 255., 5122: 32767., 5123: 65535.}


def load_glb(p):
    d = open(p, 'rb').read(); off = 12; js = None; b = b''
    while off < len(d):
        ln, typ = struct.unpack('<II', d[off:off + 8]); ch = d[off + 8:off + 8 + ln]
        if typ == 0x4E4F534A: js = json.loads(ch)
        elif typ == 0x004E4942: b = ch
        off += 8 + ln
    return js, b


def acc(js, b, i, as_int=False):
    a = js['accessors'][i]; dt = CT[a['componentType']]; n = NC[a['type']]; cnt = a['count']
    if 'bufferView' in a:
        bv = js['bufferViews'][a['bufferView']]; base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        isz = np.dtype(dt).itemsize * n; st = bv.get('byteStride', 0) or isz
        if st != isz:
            raw = np.frombuffer(b, np.uint8, count=st * (cnt - 1) + isz, offset=base)
            arr = np.lib.stride_tricks.as_strided(raw, (cnt, isz), (st, 1)).copy().view(dt).reshape(cnt, n)
        else:
            arr = np.frombuffer(b, dt, count=cnt * n, offset=base).reshape(cnt, n).copy()
    else:
        arr = np.zeros((cnt, n), dt)
    if 'sparse' in a:
        sp = a['sparse']; si = sp['indices']; sv = sp['values']
        bvi = js['bufferViews'][si['bufferView']]
        idx = np.frombuffer(b, CT[si['componentType']], count=sp['count'], offset=bvi.get('byteOffset', 0) + si.get('byteOffset', 0))
        bvv = js['bufferViews'][sv['bufferView']]
        vals = np.frombuffer(b, dt, count=sp['count'] * n, offset=bvv.get('byteOffset', 0) + sv.get('byteOffset', 0)).reshape(-1, n)
        arr = arr.copy(); arr[idx] = vals
    if as_int: return arr.astype(np.int64)
    if a.get('normalized') and a['componentType'] in NMAX:
        return np.maximum(arr.astype(np.float32) / NMAX[a['componentType']], -1)
    return arr.astype(np.float32)


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def node_mat(n):
    if 'matrix' in n: return np.array(n['matrix'], float).reshape(4, 4).T
    M = np.eye(4); R = qmat(n.get('rotation', [0, 0, 0, 1])); S = np.diag(n.get('scale', [1, 1, 1]))
    M[:3, :3] = R @ S; M[:3, 3] = n.get('translation', [0, 0, 0]); return M


def vertex_normals(P, I):
    N = np.zeros_like(P); fn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    for k in range(3): np.add.at(N, I[:, k], fn)
    return N


def flatten(js, b):
    nodes = js['nodes']; world = {}; paths = {}
    sc = js['scenes'][js.get('scene', 0)]
    def walk(i, P, path):
        n = nodes[i]; M = P @ node_mat(n); world[i] = M; pth = path + '/' + n.get('name', ''); paths[i] = pth
        for c in n.get('children', []): walk(c, M, pth)
    for r in sc['nodes']: walk(r, np.eye(4), '')
    prims = []
    for i, n in enumerate(nodes):
        if 'mesh' not in n or i not in world: continue
        mesh = js['meshes'][n['mesh']]
        for pr in mesh['primitives']:
            if pr.get('mode', 4) != 4: continue
            at = pr['attributes']
            if 'POSITION' not in at: continue
            P = acc(js, b, at['POSITION'])
            if 'skin' in n:
                sk = js['skins'][n['skin']]; J = acc(js, b, at['JOINTS_0'], True); Wt = acc(js, b, at['WEIGHTS_0'])
                ibm = acc(js, b, sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1) if 'inverseBindMatrices' in sk else np.tile(np.eye(4), (len(sk['joints']), 1, 1))
                JM = np.stack([world.get(j, np.eye(4)) @ ibm[k] for k, j in enumerate(sk['joints'])])
                Ph = np.c_[P, np.ones(len(P))]; out = np.zeros((len(P), 3))
                for k in range(4):
                    out += Wt[:, k:k + 1] * np.einsum('nij,nj->ni', JM[J[:, k]], Ph)[:, :3]
                Pw = out; M3 = np.eye(3); flip = False
            else:
                M = world[i]; Pw = P @ M[:3, :3].T + M[:3, 3]; M3 = np.linalg.inv(M[:3, :3]).T; flip = np.linalg.det(M[:3, :3]) < 0
            I = acc(js, b, pr['indices'], True).reshape(-1) if 'indices' in pr else np.arange(len(P))
            I = I[:len(I) // 3 * 3].reshape(-1, 3)
            if flip: I = I[:, ::-1]
            N = acc(js, b, at['NORMAL']) @ M3.T if 'NORMAL' in at else vertex_normals(Pw, I)
            N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
            UV = acc(js, b, at['TEXCOORD_0']) if 'TEXCOORD_0' in at else None
            mi = pr.get('material', -1)
            mname = js['materials'][mi].get('name', '') if mi >= 0 else ''
            prims.append(dict(P=Pw.astype(np.float64), N=N.astype(np.float32), UV=UV, I=I, mat=mi, mname=mname, path=paths[i] + '/' + mesh.get('name', '')))
    return prims


def tri_area(P, I):
    return 0.5 * np.linalg.norm(np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]]), axis=1)


def visible(P, I, occl, views=56, res=700):
    """True per triangle when it is seen from at least one view around the car (glass does not hide what is behind it)."""
    c = P[I].mean(1); pts = [c] + [P[I[:, k]] * .85 + c * .15 for k in range(3)]
    S = np.concatenate(pts); tid = np.tile(np.arange(len(I)), 4)
    vis = np.zeros(len(I), bool); ga = math.pi * (3 - math.sqrt(5))
    lo, hi = P.min(0), P.max(0); ctr = (lo + hi) / 2; rad = np.linalg.norm(hi - lo) / 2; S = S - ctr
    for k in range(views):
        y = min(-0.25 + 1.25 * (k + .5) / views, .999); r = math.sqrt(1 - y * y); th = ga * k
        d = np.array([math.cos(th) * r, y, math.sin(th) * r])
        a = np.cross(d, [0, 1, 0]) if abs(d[1]) < .99 else np.array([1., 0, 0]); a /= np.linalg.norm(a); bb = np.cross(d, a)
        u = S @ a; v = S @ bb; dep = -(S @ d)
        px = np.clip(((u + rad) / (2 * rad) * res).astype(np.int64), 0, res - 1); py = np.clip(((v + rad) / (2 * rad) * res).astype(np.int64), 0, res - 1)
        pix = py * res + px; order = np.lexsort((dep, pix)); ps = pix[order]
        first = np.r_[True, ps[1:] != ps[:-1]]; win = order[first]; vis[tid[win]] = True
        tw = tid[win]; tr = ~occl[tw]
        if tr.any():
            pos = np.nonzero(first)[0][tr]
            for step in (1, 2, 3):
                nxt = pos + step; ok = nxt < len(order); nxt = nxt[ok]; same = ps[nxt] == ps[pos[ok]]
                vis[tid[order[nxt[same]]]] = True
    return vis


def cluster(P, N, UV, C, I, cell):
    q = np.floor(P / cell).astype(np.int64)
    ax = np.argmax(np.abs(N), 1); sg = (N[np.arange(len(N)), ax] > 0).astype(np.int64)
    key = np.c_[q, ax * 2 + sg]
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1); m = len(first); cnt = np.bincount(inv, minlength=m).astype(np.float64)
    Pn = np.stack([np.bincount(inv, P[:, k], m) for k in range(3)], 1) / cnt[:, None]
    Nn = np.stack([np.bincount(inv, N[:, k], m) for k in range(3)], 1); Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    UVn = UV[first] if UV is not None else None; Cn = C[first] if C is not None else None
    J = inv[I]; ok = (J[:, 0] != J[:, 1]) & (J[:, 1] != J[:, 2]) & (J[:, 0] != J[:, 2]); J = J[ok]
    if len(J):
        s = np.sort(J, 1); _, u = np.unique(s, axis=0, return_index=True); J = J[np.sort(u)]
    used = np.unique(J); remap = -np.ones(m, np.int64); remap[used] = np.arange(len(used))
    return Pn[used], Nn[used].astype(np.float32), (UVn[used] if UVn is not None else None), (Cn[used] if Cn is not None else None), remap[J]


def decimate_groups(groups, target, lo_cell=0.002, hi_cell=0.5):
    """One cell size for all groups, binary-searched so the total triangle count fits the target."""
    if sum(len(g['I']) for g in groups) <= target: return groups
    a, bnd = lo_cell, hi_cell; best = None; out = groups
    for _ in range(14):
        cell = math.sqrt(a * bnd)
        out = [dict(g, **dict(zip(('P', 'N', 'UV', 'C', 'I'), cluster(g['P'], g['N'], g['UV'], g['C'], g['I'], cell)))) for g in groups]
        t = sum(len(g['I']) for g in out)
        if t > target: a = cell
        else: bnd = cell; best = out
        if best is not None and target * .9 < t <= target: break
    return best if best is not None else out


def tex_image(js, b, ti, maxs):
    t = js['textures'][ti]; src = t.get('source')
    if src is None:
        for e in t.get('extensions', {}).values():
            if 'source' in e: src = e['source']
    if src is None: return None
    im = js['images'][src]
    if 'bufferView' not in im: return None
    bv = js['bufferViews'][im['bufferView']]; data = b[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
    try:
        img = Image.open(io.BytesIO(data)); img.load()
    except Exception:
        return None
    img = img.convert('RGBA'); w, h = img.size; s = min(1, maxs / max(w, h))
    if s < 1: img = img.resize((max(4, int(w * s)), max(4, int(h * s))), Image.LANCZOS)
    return img


def srgb(c): return [float(min(1, max(0, x)) ** (1 / 2.2)) for x in c[:3]]


JUNK_RE = re.compile(r'blur|damage|shadow_?plane|ground_?shadow|lod_?[b-z]\b|_lod[1-9]|collision|lowpoly_shadow', re.I)
WHEEL_RE = re.compile(r'ty(re|res)\b|tyre|tire|wheel|rim\b|rims|_rim|rim_|\brim|whl|lug|hub|rotor|brake.?dis|disc|disk|valve', re.I)
CALIPER_RE = re.compile(r'cal+ip', re.I)
NOT_WHEEL_RE = re.compile(r'steer|sw_|steering', re.I)
GLASS_RE = re.compile(r'glass|window|windscreen|windshield|vetro|transp', re.I)
PAINT_RE = re.compile(r'paint|coloured|colored|carbody|\bbody\b|^body|wccarbody|livery', re.I)
HEAD_RE = re.compile(r'head|front.?light|frontlight|lightsss|front_light|lamp_f|light_f', re.I)
TAIL_RE = re.compile(r'rear.?l|tail|brake.?light|brakelight|stop|rearlamp', re.I)


def convert(cfg, out_dir, preview_dir=None):
    js, b = load_glb(cfg['src'])
    prims = [p for p in flatten(js, b) if not JUNK_RE.search(p['path'] + ' ' + p['mname'])]
    for pat in cfg.get('drop', []):
        prims = [p for p in prims if not re.search(pat, p['path'] + ' ' + p['mname'], re.I)]
    def is_shadow(p):
        e = np.ptp(p['P'], 0); return e[1] < .02 and e[0] * e[2] > 1.5 and e[0] > 1.2
    prims = [p for p in prims if not is_shadow(p)]
    mats = js.get('materials', [])
    P, N, UV, I, tm, twn, tcal = [], [], [], [], [], [], []; off = 0
    for p in prims:
        P.append(p['P']); N.append(p['N']); I.append(p['I'] + off)
        UV.append(p['UV'] if p['UV'] is not None else np.zeros((len(p['P']), 2), np.float32))
        nm = p['path'] + ' ' + p['mname']; own = '/'.join(p['path'].split('/')[-2:]) + ' ' + p['mname']
        tm.append(np.full(len(p['I']), p['mat'])); twn.append(np.full(len(p['I']), bool(WHEEL_RE.search(nm)) and not NOT_WHEEL_RE.search(own)))
        tcal.append(np.full(len(p['I']), bool(CALIPER_RE.search(nm)))); off += len(p['P'])
    P = np.concatenate(P); N = np.concatenate(N); UV = np.concatenate(UV).astype(np.float32); I = np.concatenate(I)
    tm = np.concatenate(tm); twn = np.concatenate(twn); tcal = np.concatenate(tcal)
    ok = tri_area(P, I) > 1e-12; I, tm, twn, tcal = I[ok], tm[ok], twn[ok], tcal[ok]
    # orientation: length along Z, metres, centred, on the ground
    if cfg.get('upz'):
        P = P[:, [0, 2, 1]] * [1, 1, -1]; N = N[:, [0, 2, 1]] * [1, 1, -1]; I = I[:, ::-1]
    ext = P.max(0) - P.min(0)
    if ext[0] > ext[2]:
        P = np.c_[-P[:, 2], P[:, 1], P[:, 0]]; N = np.c_[-N[:, 2], N[:, 1], N[:, 0]]
    L = P[:, 2].max() - P[:, 2].min()
    P = P * (cfg.get('scale') or (1.0 if 3.6 <= L <= 6.2 else 4.55 / L))
    lo, hi = P.min(0), P.max(0); P[:, 0] -= (lo[0] + hi[0]) / 2; P[:, 2] -= (lo[2] + hi[2]) / 2; P[:, 1] -= lo[1]
    def mname(mi): return mats[mi].get('name', '') if mi >= 0 else ''
    def is_glass(mi):
        if mi < 0: return False
        m = mats[mi]; a = m.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1])[3]
        return bool(GLASS_RE.search(mname(mi))) or 'KHR_materials_transmission' in m.get('extensions', {}) or (m.get('alphaMode') == 'BLEND' and a < .9)
    glass_tri = np.array([is_glass(m) for m in tm])
    # front is where the headlights are
    tc = P[I].mean(1)
    head = np.array([bool(HEAD_RE.search(mname(m))) for m in tm]); tail = np.array([bool(TAIL_RE.search(mname(m))) for m in tm])
    if cfg.get('flip') is not None: flip = cfg['flip']
    elif head.any() and tail.any(): flip = tc[head, 2].mean() < tc[tail, 2].mean()
    elif head.any(): flip = tc[head, 2].mean() < 0
    elif tail.any(): flip = tc[tail, 2].mean() > 0
    else: flip = False
    if flip: P = P * [-1, 1, -1]; N = N * [-1, 1, -1]
    # stray far-away parts (light cones, flares) and flat ground planes
    vw = np.unique(I); q0 = np.percentile(P[vw], 1, axis=0); q1 = np.percentile(P[vw], 99, axis=0); pad = (q1 - q0) * .06 + .05
    inb = np.all((P[I] >= q0 - pad) & (P[I] <= q1 + pad), axis=(1, 2))
    gy = P[vw, 1].min(); flat = np.all(P[I][:, :, 1] < gy + .012, axis=1)
    keep = inb & ~flat; I, tm, twn, tcal, glass_tri = I[keep], tm[keep], twn[keep], tcal[keep], glass_tri[keep]
    vw = np.unique(I); lo, hi = P[vw].min(0), P[vw].max(0)
    P[:, 0] -= (lo[0] + hi[0]) / 2; P[:, 2] -= (lo[2] + hi[2]) / 2; P[:, 1] -= lo[1]
    # hidden triangles go
    vis = visible(P, I, ~glass_tri) | twn
    I, tm, twn, tcal, glass_tri = I[vis], tm[vis], twn[vis], tcal[vis], glass_tri[vis]
    tc = P[I].mean(1); H = P[:, 1].max()
    # wheels: one per corner from the wheel-named triangles
    wheels = []; wsel = twn & ~tcal
    if wsel.sum() > 50:
        for zs in (1, -1):
            for xs in (1, -1):
                m = wsel & (np.sign(tc[:, 0]) == xs) & (np.sign(tc[:, 2]) == zs) & (tc[:, 1] < H * .6)
                if m.sum() < 20: continue
                vv = P[np.unique(I[m])]
                y0, y1 = vv[:, 1].min(), vv[:, 1].max(); z0, z1 = vv[:, 2].min(), vv[:, 2].max()
                wheels.append(dict(x=float((vv[:, 0].min() + vv[:, 0].max()) / 2), y=float((y0 + y1) / 2), z=float((z0 + z1) / 2),
                                   r=float(max(y1 - y0, z1 - z0) / 2), w=float(vv[:, 0].max() - vv[:, 0].min()), front=zs > 0))
    tw = -np.ones(len(I), np.int64)
    for k, w in enumerate(wheels):
        d = np.hypot(tc[:, 1] - w['y'], tc[:, 2] - w['z'])
        tw[(d < w['r'] * 1.08) & (np.abs(tc[:, 0] - w['x']) < w['w'] * .75 + .05) & wsel] = k
    if wheels:
        g = min(w['y'] - w['r'] for w in wheels); P[:, 1] -= g
        for w in wheels: w['y'] -= g
    used_m = sorted(set(tm.tolist())); area = tri_area(P, I)
    marea = {m: float(area[tm == m].sum()) for m in used_m}
    paint = cfg.get('paint')
    if paint is None:
        cands = [m for m in used_m if m >= 0 and PAINT_RE.search(mname(m)) and not re.search(r'\bint', mname(m), re.I) and not is_glass(m)]
        pool = cands or [m for m in used_m if m >= 0 and not is_glass(m) and not (twn[tm == m].mean() > .5)]
        paint = max(pool, key=lambda m: marea[m]) if pool else -1
    else:
        paint = [i for i, m in enumerate(mats) if m.get('name') == paint][0]
    # textures: loaded lazily, packed only when a material keeps its map
    tex_list = []; img_cache = {}; packed = {}
    def get_img(ti, maxs):
        if (ti, maxs) not in img_cache: img_cache[(ti, maxs)] = tex_image(js, b, ti, maxs)
        return img_cache[(ti, maxs)]
    def pack(ti, maxs):
        if (ti, maxs) in packed: return packed[(ti, maxs)]
        img = get_img(ti, maxs)
        if img is None: return None
        buf = io.BytesIO()
        if np.array(img)[:, :, 3].min() < 250: img.save(buf, 'PNG', optimize=True); mime = 'image/png'
        else: img.convert('RGB').save(buf, 'JPEG', quality=80); mime = 'image/jpeg'
        tex_list.append(dict(mime=mime, data=buf.getvalue())); packed[(ti, maxs)] = len(tex_list) - 1
        return packed[(ti, maxs)]
    matinfo = {}
    for m in used_m:
        if m < 0:
            matinfo[m] = dict(name='', color=[.6, .6, .6], metal=0, rough=.6, kind='plain', map=None, img=None, alpha=1, emi=[0, 0, 0], alphaMode='OPAQUE', double=True, clear=0); continue
        md = mats[m]; pbr = md.get('pbrMetallicRoughness', {}); bc = pbr.get('baseColorFactor', [1, 1, 1, 1]); ext = md.get('extensions', {})
        info = dict(name=md.get('name', ''), color=srgb(bc), metal=float(pbr.get('metallicFactor', 1)), rough=float(pbr.get('roughnessFactor', 1)),
                    alpha=float(bc[3]), emi=srgb(md.get('emissiveFactor', [0, 0, 0])), map=None, img=None, emap=None, alphaMode=md.get('alphaMode', 'OPAQUE'),
                    double=bool(md.get('doubleSided')), clear=float(ext.get('KHR_materials_clearcoat', {}).get('clearcoatFactor', 0)))
        if 'KHR_materials_emissive_strength' in ext:
            info['emi'] = [min(1, c * ext['KHR_materials_emissive_strength'].get('emissiveStrength', 1)) for c in info['emi']]
        if 'baseColorTexture' in pbr:
            ti = pbr['baseColorTexture']['index']; tt = pbr['baseColorTexture'].get('extensions', {}).get('KHR_texture_transform')
            if tt: info['tt'] = tt
            if m == paint or marea.get(m, 0) > .2:
                mx = 512 if (m == paint or marea.get(m, 0) > .5) else 256
                info['img'] = get_img(ti, mx); info['tex'] = (ti, mx)
            else:
                info['img'] = get_img(ti, 48)
        if is_glass(m): info['kind'] = 'glass'
        elif m == paint: info['kind'] = 'paint'
        elif sum(info['emi']) > .15 or re.search(r'glow|emiss|bulb|led', info['name'], re.I): info['kind'] = 'light'
        elif info.get('tex') and info['img'] is not None: info['kind'] = 'tex'
        else: info['kind'] = 'metal' if info['metal'] > .5 else 'plain'
        if info['kind'] in ('paint', 'tex') and info.get('tex') and info['img'] is not None: info['map'] = pack(*info['tex'])
        matinfo[m] = info
    for m, info in matinfo.items():
        tt = info.get('tt')
        if not tt: continue
        vi = np.unique(I[tm == m]); o = tt.get('offset', [0, 0]); sc = tt.get('scale', [1, 1]); r = tt.get('rotation', 0)
        u, v = UV[vi, 0] * sc[0], UV[vi, 1] * sc[1]; cr, sr = math.cos(r), math.sin(r)
        UV[vi, 0] = cr * u + sr * v + o[0]; UV[vi, 1] = -sr * u + cr * v + o[1]
    def vcolors(vi, info):
        col = np.tile(np.array(info['color']) * 255, (len(vi), 1))
        if info['img'] is not None:
            arr = np.asarray(info['img'].convert('RGB')).astype(np.float32); h, w = arr.shape[:2]
            px = np.clip((np.mod(UV[vi, 0], 1) * w).astype(int), 0, w - 1); py = np.clip((np.mod(UV[vi, 1], 1) * h).astype(int), 0, h - 1)
            col = col * arr[py, px] / 255
        return np.clip(np.c_[col, np.full((len(vi), 1), 255.0)], 0, 255).astype(np.uint8)
    def bucket_of(m, lod):
        k = matinfo[m]['kind']
        if lod == 'lo':
            if k == 'glass': return ('glass', -1)
            if k == 'paint': return ('paint', m if matinfo[m]['map'] is not None else -1)
            if k == 'light': return ('light', -1)
            return ('vmetal' if matinfo[m]['metal'] > .5 or k == 'metal' else 'vplain', -1)
        if k in ('paint', 'tex'): return (k, m)
        if k in ('glass', 'light'): return (k, -1)
        return ('vmetal' if k == 'metal' else 'vplain', -1)
    out_parts = {'hi': [], 'lo': []}; budgets = cfg.get('budget', {'hi': 42000, 'lo': 9000})
    for lod in ('hi', 'lo'):
        for wk in [-1] + list(range(len(wheels))):
            sel = tw == wk
            if not sel.any(): continue
            groups = {}
            for m in used_m:
                ms = sel & (tm == m)
                if not ms.any(): continue
                bk = bucket_of(m, lod) if wk < 0 else (('vmetal' if matinfo[m]['metal'] > .4 else 'vplain'), -1)
                if lod == 'hi' and wk >= 0 and matinfo[m]['map'] is not None and matinfo[m]['kind'] != 'glass': bk = ('tex', m)
                groups.setdefault(bk, []).append(ms)
            glist = []
            for bk, masks in groups.items():
                ms = np.any(masks, 0); It = I[ms]; vi, inv = np.unique(It, return_inverse=True); inv = inv.reshape(-1, 3); mlist = tm[ms]
                C = None
                if bk[0] in ('vmetal', 'vplain', 'light', 'glass', 'paint'):
                    C = np.zeros((len(vi), 4), np.uint8)
                    for m in np.unique(mlist):
                        vv = np.unique(inv[mlist == m]); C[vv] = vcolors(vi[vv], matinfo[m])
                glist.append(dict(P=P[vi], N=N[vi], UV=UV[vi], C=C, I=inv, bk=bk, mats=sorted(set(mlist.tolist()))))
            tgt = budgets[lod] if wk < 0 else (budgets[lod] // 18 if lod == 'hi' else budgets[lod] // 30)
            for g in decimate_groups(glist, tgt, lo_cell=.0015, hi_cell=.4):
                if len(g['I']): out_parts[lod].append(dict(g, wheel=wk))
    mrec = []; mindex = {}
    def mat_record(bk, mats_in):
        if bk in mindex: return mindex[bk]
        kind, m = bk; rec = dict(kind=kind)
        if kind in ('tex', 'paint', 'light', 'glass') and m != -1:
            info = matinfo[m]
            rec.update(color=info['color'], metal=round(info['metal'], 3), rough=round(info['rough'], 3), map=info['map'], emap=info.get('emap'), emi=info['emi'],
                       alpha=info['alpha'], blend=info['alphaMode'], double=info['double'], clear=info.get('clear', 0))
        else:
            ms = [matinfo[x] for x in mats_in]
            rec.update(color=[1, 1, 1], metal=round(float(np.mean([x['metal'] for x in ms])), 3), rough=round(float(np.mean([x['rough'] for x in ms])), 3), map=None, emap=None,
                       emi=[0, 0, 0], alpha=float(np.mean([x['alpha'] for x in ms])), blend='OPAQUE', double=True, clear=0, vc=True)
            if kind == 'glass': rec.update(alpha=min(.75, rec['alpha']) if rec['alpha'] < 1 else .55, blend='BLEND')
            if kind == 'light': rec['emi'] = [1, 1, 1]
            if kind == 'paint': rec.update(clear=1)
        if kind == 'vmetal': rec['metal'] = max(rec['metal'], .7); rec['rough'] = min(rec['rough'], .35)
        if kind == 'paint' and m != -1 and matinfo[m]['img'] is not None:
            a = np.asarray(matinfo[m]['img'].convert('RGB').resize((64, 64))).astype(float) / 255
            sat = ((a.max(2) - a.min(2)) / (a.max(2) + 1e-6)).mean()
            if sat < .08:   # a grey paint texture can be recoloured with team colours
                rec['tint'] = True; rec['tlum'] = round(float(a.mean()), 3)
                if a.mean() < .2: rec['nomap'] = True
        mrec.append(rec); mindex[bk] = len(mrec) - 1; return mindex[bk]
    blob = bytearray()
    def push(arr):
        nonlocal blob
        while len(blob) % 4: blob.append(0)
        o = len(blob); blob += arr.tobytes(); return o
    parts_json = {'hi': [], 'lo': []}
    for lod in ('hi', 'lo'):
        for g in out_parts[lod]:
            mi = mat_record(g['bk'], g['mats']); rec = mrec[mi]; Pp = g['P'].copy()
            if g['wheel'] >= 0:
                w = wheels[g['wheel']]; Pp -= [w['x'], w['y'], w['z']]
            pmin = Pp.min(0); rng = np.maximum(Pp.max(0) - pmin, 1e-6)
            ent = dict(wheel=int(g['wheel']), mat=mi, v=int(len(Pp)), t=int(len(g['I'])), pmin=pmin.round(5).tolist(), prng=rng.round(5).tolist())
            ent['pos'] = push(np.round((Pp - pmin) / rng * 65535 - 32768).astype(np.int16))
            ent['nor'] = push(np.c_[np.round(g['N'] * 127), np.zeros(len(g['N']))].astype(np.int8))
            if rec.get('map') is not None or rec.get('emap') is not None:
                uv = g['UV']; umin = uv.min(0); urng = np.maximum(uv.max(0) - umin, 1e-6)
                ent['uv'] = push(np.round((uv - umin) / urng * 65535).astype(np.uint16)); ent['umin'] = umin.round(6).tolist(); ent['urng'] = urng.round(6).tolist()
            if rec.get('vc') or (g['C'] is not None and rec['kind'] in ('paint', 'glass', 'light')):
                ent['col'] = push((g['C'] if g['C'] is not None else np.full((len(Pp), 4), 255, np.uint8)).astype(np.uint8))
            ent['i32'] = len(Pp) >= 65536; ent['idx'] = push(g['I'].astype(np.uint32 if ent['i32'] else np.uint16))
            parts_json[lod].append(ent)
    texj = [dict(mime=t['mime'], off=push(np.frombuffer(t['data'], np.uint8)), len=len(t['data'])) for t in tex_list]
    tcn = P[I].mean(1)
    def light_pos(mask, front):
        if not mask.any(): return None
        out = []
        for xs in (-1, 1):
            m = mask & (np.sign(tcn[:, 0]) == xs) & ((tcn[:, 2] > 0) if front else (tcn[:, 2] < 0))
            if m.sum() < 3: return None
            c = tcn[m].mean(0); out.append([round(float(c[0]), 3), round(float(c[1]), 3), round(float(c[2] + (.05 if front else -.05)), 3)])
        return out
    headm = np.array([bool(HEAD_RE.search(mname(m))) for m in tm]); tailm = np.array([bool(TAIL_RE.search(mname(m))) for m in tm])
    vw = np.unique(I); L = float(np.ptp(P[vw, 2])); Wd = float(np.ptp(P[vw, 0])); H = float(P[vw, 1].max())
    hd = light_pos(headm, True) or [[-Wd * .33, H * .45, L / 2 - .1], [Wd * .33, H * .45, L / 2 - .1]]
    tl = light_pos(tailm, False) or [[-Wd * .33, H * .55, -L / 2 + .05], [Wd * .33, H * .55, -L / 2 + .05]]
    ex = (js.get('asset', {}).get('extras', {}) or {})
    hdr = dict(id=cfg['id'], name=cfg['name'], L=round(L, 3), W=round(Wd, 3), H=round(H, 3),
               wheels=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in w.items()} for w in wheels],
               mats=[{k: v for k, v in r.items() if v is not None} for r in mrec], tex=texj, parts=parts_json, head=hd, tail=tl,
               credit=dict(title=ex.get('title', ''), author=ex.get('author', ''), license=ex.get('license', ''), source=ex.get('source', '')))
    hj = json.dumps(hdr, separators=(',', ':')).encode()
    while len(hj) % 4: hj += b' '
    data = b'NAGP' + struct.pack('<I', len(hj)) + hj + bytes(blob)
    open(os.path.join(out_dir, cfg['id'] + '.car'), 'wb').write(data)
    return dict(id=cfg['id'], kb=len(data) // 1024, hi=sum(p['t'] for p in parts_json['hi']), lo=sum(p['t'] for p in parts_json['lo']),
                wheels=len(wheels), L=hdr['L'], W=hdr['W'], H=hdr['H'], paint=mname(paint), flip=bool(flip))


if __name__ == '__main__':
    cfgs = json.load(open(sys.argv[1])); out = sys.argv[2]; only = sys.argv[4:] if len(sys.argv) > 4 else None
    os.makedirs(out, exist_ok=True)
    for c in cfgs:
        if only and c['id'] not in only: continue
        try:
            print(json.dumps(convert(c, out)))
        except Exception as e:
            import traceback; traceback.print_exc(); print('FAILED', c['id'], e)
        sys.stdout.flush()
