"""Repair wheel pivots in .car files so every tyre spins on its own axle and the car sits on the ground.

Usage: python3 tools/fixwheels.py cars/*.car      (files are fixed in place)

Some source models name extra parts "wheel" (arches, axles, spare parts). The converter then
grouped those with a tyre and put the spin pivot in the wrong place: the wheel wobbled and the
whole car floated. This tool finds the real tyre ring, moves the pivot to its centre, drops
stray triangles that are not part of the wheel and lowers the car onto the ground.
"""
import sys
import numpy as np
from carfile import CarFile


def wheel_vertices(cf, k, lod='hi'):
    out = []
    w = cf.hdr['wheels'][k]
    for p in cf.hdr['parts'][lod]:
        if p['wheel'] == k:
            out.append(cf.positions(p) + [w['x'], w['y'], w['z']])
    return np.concatenate(out) if out else np.zeros((0, 3))


def is_good(V, w):
    rel = V - [w['x'], w['y'], w['z']]
    ey = np.ptp(rel[:, 1]) / 2
    ez = np.ptp(rel[:, 2]) / 2
    cy = (rel[:, 1].max() + rel[:, 1].min()) / 2
    cz = (rel[:, 2].max() + rel[:, 2].min()) / 2
    return abs(ey - w['r']) < .03 and abs(ez - w['r']) < .03 and abs(cy) < .03 and abs(cz) < .03 and np.ptp(rel[:, 0]) < .55


def fit_ring(V, side):
    """Robust tyre centre and radius: median centre, drop far-away stray parts, then the trimmed extents."""
    S = V[np.sign(V[:, 0]) == side] if np.count_nonzero(np.sign(V[:, 0]) == side) > 50 else V
    c = np.median(S[:, 1:], axis=0)
    for _ in range(3):
        d = np.hypot(S[:, 1] - c[0], S[:, 2] - c[1])
        K = S[d < 2.2 * np.median(d)]
        y0, y1 = np.percentile(K[:, 1], [.5, 99.5])
        z0, z1 = np.percentile(K[:, 2], [.5, 99.5])
        c = np.array([(y0 + y1) / 2, (z0 + z1) / 2])
    r = max(y1 - y0, z1 - z0) / 2
    d = np.hypot(S[:, 1] - c[0], S[:, 2] - c[1])
    ring = S[d < r * 1.08]
    x0, x1 = np.percentile(ring[:, 0], [2, 98])
    return dict(x=float((x0 + x1) / 2), y=float(c[0]), z=float(c[1]), r=float(r), w=float(min(x1 - x0, .5)))


def fix(path):
    cf = CarFile(path)
    H = cf.hdr
    W = H['wheels']
    if len(W) != 4:
        print(path, 'skipped: no 4 wheels')
        return
    V = [wheel_vertices(cf, k) for k in range(4)]
    good = [is_good(V[k], W[k]) for k in range(4)]
    if all(good):
        print(path, 'wheels ok')
        new = [dict(w) for w in W]
    else:
        new = []
        for k, w in enumerate(W):
            if good[k]:
                new.append(dict(w))
                continue
            f = fit_ring(V[k], np.sign(w['x']) or 1)
            f['front'] = w['front']
            new.append(f)
            print(f"{path} wheel {k}: pivot ({w['x']:.2f},{w['y']:.2f},{w['z']:.2f}) r={w['r']:.2f} -> ({f['x']:.2f},{f['y']:.2f},{f['z']:.2f}) r={f['r']:.2f}")
    # move pivots and drop stray triangles
    for lod, p in cf.all_parts():
        k = p['wheel']
        if k < 0:
            continue
        o, n = W[k], new[k]
        shift = np.array([o['x'] - n['x'], o['y'] - n['y'], o['z'] - n['z']])
        if np.abs(shift).max() > 1e-6:
            p['pmin'] = [round(float(a + b), 5) for a, b in zip(p['pmin'], shift)]
        P = cf.positions(p)
        I = cf.indices(p)
        c = P[I].mean(1)
        keep = (np.hypot(c[:, 1], c[:, 2]) < n['r'] * 1.12) & (np.abs(c[:, 0]) < n['w'] / 2 + .08)
        if not keep.all():
            cf.set_indices(p, I[keep])
    # sit the car on the ground
    g = min(w['y'] - w['r'] for w in new)
    if abs(g) > .005:
        for lod, p in cf.all_parts():
            if p['wheel'] < 0:
                p['pmin'][1] = round(p['pmin'][1] - g, 5)
        for w in new:
            w['y'] -= g
        for lst in (H['head'], H['tail']):
            for pt in lst:
                pt[1] = round(pt[1] - g, 3)
        H['H'] = round(H['H'] - g, 3)
        print(f'{path}: lowered by {g:.3f} m')
    H['wheels'] = [{kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in w.items()} for w in new]
    cf.save(path)


if __name__ == '__main__':
    for f in sys.argv[1:]:
        fix(f)
