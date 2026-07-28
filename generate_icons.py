#!/usr/bin/env python3
"""Generate PNG icons + wrap them into ICO files (no dependencies)."""
import struct, zlib, os

def make_png(size, r, g, b):
    """Create solid-color square PNG with letter overlay."""
    lw = max(1, size // 25)
    lh = size // 3
    cx, cy = size // 2, size // 2
    
    raw = b''
    for y in range(size):
        raw += b'\x00'  # filter none
        for x in range(size):
            on = abs(x - cy) < lw and abs(y - cy) < lh  # crosshair
            raw += bytes([255, 255, 255, 255] if on else [r, g, b, 255])
    
    def ch(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    
    return (b'\x89PNG\r\n\x1a\n'
        + ch(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
        + ch(b'IDAT', zlib.compress(raw))
        + ch(b'IEND', b''))

def pngs_to_ico(png_bytes_list):
    """Wrap PNG bytes into ICO."""
    header = struct.pack('<HHH', 0, 1, len(png_bytes_list))
    entries = b''
    off = 6 + 16 * len(png_bytes_list)
    for d in png_bytes_list:
        w = struct.unpack('>I', d[16:20])[0]
        h = struct.unpack('>I', d[20:24])[0]
        entries += struct.pack('<BBBBHHII',
            0 if w >= 256 else w, 0 if h >= 256 else h,
            0, 0, 1, 32, len(d), off)
        off += len(d)
    return header + entries + b''.join(png_bytes_list)

D = 'static/icons'
os.makedirs(D, exist_ok=True)

for label, color in [('lan', (34, 139, 34)), ('web', (30, 100, 180))]:
    # PNG files
    for sz in [192, 512]:
        path = f'{D}/icon-{label}-{sz}.png'
        with open(path, 'wb') as f:
            f.write(make_png(sz, *color))
        print(f'  {path}')
    
    # ICO file (contains both sizes)
    pngs = []
    for sz in [192, 512]:
        with open(f'{D}/icon-{label}-{sz}.png', 'rb') as f:
            pngs.append(f.read())
    ico_path = f'{D}/favicon-{label}.ico'
    with open(ico_path, 'wb') as f:
        f.write(pngs_to_ico(pngs))
    print(f'  {ico_path}')

print('Done!')
