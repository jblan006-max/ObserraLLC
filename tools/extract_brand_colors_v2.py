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
img = img.resize((400, 400))
px = list(img.getdata())
px = [p for p in px if p[3] > 10]

# count exact colors but downsample to reduce noise
def quantize(c, q=16):
    return tuple((int(floor(v/(256/q))*(256//q)) for v in c[:3]))

cnt = Counter(quantize(p, q=32) for p in px)
most = cnt.most_common(30)

def rgb_to_hex(c):
    return '#%02x%02x%02x' % c

def rgb_to_hsl_vals(c):
    r, g, b = [x/255.0 for x in c]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h*360, s*100, l*100)

palette = []
for col, ccount in most:
    h, s, l = rgb_to_hsl_vals(col)
    palette.append({
        'rgb': col,
        'hex': rgb_to_hex(col),
        'h': round(h,1), 's': round(s,1), 'l': round(l,1),
        'count': ccount
    })

# pick darkest non-transparent color (lowest lightness) with enough count
candidates = [p for p in palette if p['count']>10]
if not candidates:
    candidates = palette
# sort by lightness ascending then by count descending
candidates.sort(key=lambda x: (x['l'], -x['count']))
primary = candidates[0] if candidates else None

# also pick most saturated color
sat_candidates = sorted(palette, key=lambda x: (-x['s'], -x['count']))
secondary = sat_candidates[0] if sat_candidates else None

import json
print(json.dumps({'primary': primary, 'secondary': secondary, 'palette': palette}, indent=2))
