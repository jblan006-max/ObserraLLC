from collections import Counter
from math import floor
import colorsys
import sys

try:
    from PIL import Image
except Exception as e:
    print('MISSING_PIL')
    print(str(e))
    sys.exit(2)

img_path = 'frontend/public/brand-mark.png'

try:
    img = Image.open(img_path).convert('RGBA')
except Exception as e:
    print('ERROR_OPEN')
    print(str(e))
    sys.exit(3)

# Resize to speed up
img = img.resize((200, 200))
px = list(img.getdata())

# Filter out transparent
px = [p for p in px if p[3] > 40]

def round_color(c, step=8):
    return tuple((int(floor(v/step)*step) for v in c[:3]))

cnt = Counter(round_color(p) for p in px)
most = cnt.most_common(12)

def rgb_to_hex(c):
    return '#%02x%02x%02x' % c

def rgb_to_hsl(c):
    r, g, b = [x/255.0 for x in c]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    # colorsys returns H,L,S where L is lightness; convert to H S L order and percent
    return (round(h*360), f"{round(s*100)}%", f"{round(l*100)}%")

palette = []
for col, ccount in most:
    palette.append({
        'rgb': col,
        'hex': rgb_to_hex(col),
        'hsl': rgb_to_hsl(col),
        'count': ccount
    })

# Pick primary as the most common non-near-white/black
primary = None
for p in palette:
    r,g,b = p['rgb']
    if not (r>230 and g>230 and b>230) and not (r<20 and g<20 and b<20):
        primary = p
        break
if primary is None and palette:
    primary = palette[0]

# secondary = next most distinct
secondary = None
for p in palette:
    if p is primary:
        continue
    # skip very close colors
    dr = abs(p['rgb'][0]-primary['rgb'][0])
    dg = abs(p['rgb'][1]-primary['rgb'][1])
    db = abs(p['rgb'][2]-primary['rgb'][2])
    if dr+dg+db > 40:
        secondary = p
        break
if secondary is None and len(palette)>1:
    secondary = palette[1]

out = {
    'primary': primary,
    'secondary': secondary,
    'palette': palette
}

import json
print(json.dumps(out, indent=2))
