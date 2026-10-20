"""Read and write Nitro Arena .car files (quantised game-ready car models).

File layout: b'NAGP' | uint32 header length | JSON header (padded to 4 bytes) | binary blob.
Each part in header.parts.hi / header.parts.lo points into the blob:
  pos  int16 x3   (quantised between pmin and pmin+prng)
  nor  int8  x4   (normal, w unused)
  uv   uint16 x2  (optional, quantised between umin and umin+urng)
  col  uint8 x4   (optional vertex colour)
  idx  uint16/uint32 triangle indices
Wheel parts (wheel >= 0) are stored relative to their wheel pivot in header.wheels.
"""
import json, struct
import numpy as np


class CarFile:
    def __init__(self, path):
        d = open(path, 'rb').read()
        assert d[:4] == b'NAGP', 'not a .car file'
        jl = struct.unpack('<I', d[4:8])[0]
        self.hdr = json.loads(d[8:8 + jl])
        self.blob = bytearray(d[8 + jl:])

    # ---- low level -------------------------------------------------------
    def _arr(self, off, dtype, count):
        return np.frombuffer(bytes(self.blob[off:off + np.dtype(dtype).itemsize * count]), dtype=dtype).copy()

    def push(self, arr):
        while len(self.blob) % 4:
            self.blob.append(0)
        off = len(self.blob)
        self.blob += np.ascontiguousarray(arr).tobytes()
        return off

    def positions(self, p):
        q = self._arr(p['pos'], np.int16, p['v'] * 3).reshape(-1, 3).astype(np.float64)
        return np.array(p['pmin']) + (q + 32768) / 65535 * np.array(p['prng'])

    def indices(self, p):
        return self._arr(p['idx'], np.uint32 if p.get('i32') else np.uint16, p['t'] * 3).reshape(-1, 3).astype(np.int64)

    def set_indices(self, p, I):
        I = np.asarray(I, np.int64).reshape(-1, 3)
        p['t'] = int(len(I))
        p['i32'] = bool(p['v'] >= 65536)
        p['idx'] = self.push(I.astype(np.uint32 if p['i32'] else np.uint16))

    def all_parts(self):
        for lod in ('hi', 'lo'):
            for p in self.hdr['parts'][lod]:
                yield lod, p

    # ---- write -------------------------------------------------------------
    def save(self, path):
        # compact: rewrite every referenced buffer into a fresh blob
        old = self.blob
        self.blob = bytearray()
        def copy(off, nbytes):
            return self.push(np.frombuffer(bytes(old[off:off + nbytes]), np.uint8))
        for _, p in self.all_parts():
            p['pos'] = copy(p['pos'], p['v'] * 6)
            p['nor'] = copy(p['nor'], p['v'] * 4)
            if p.get('uv') is not None:
                p['uv'] = copy(p['uv'], p['v'] * 4)
            if p.get('col') is not None:
                p['col'] = copy(p['col'], p['v'] * 4)
            p['idx'] = copy(p['idx'], p['t'] * 3 * (4 if p.get('i32') else 2))
        for t in self.hdr['tex']:
            t['off'] = copy(t['off'], t['len'])
        hj = json.dumps(self.hdr, separators=(',', ':')).encode()
        while len(hj) % 4:
            hj += b' '
        open(path, 'wb').write(b'NAGP' + struct.pack('<I', len(hj)) + hj + bytes(self.blob))
