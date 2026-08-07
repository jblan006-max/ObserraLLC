from PIL import Image, ImageDraw, ImageFont
import os, glob

PUB = "/app/frontend/public"
MARK_SRC = "/tmp/off_2.png"      # official square eye+keyhole
LOCK_SRC = "/tmp/off_1.webp"     # official horizontal lockup

def transparent_white(img):
    """White artwork on dark navy -> transparent white PNG, trimmed."""
    img = img.convert("RGBA")
    L = img.convert("L")
    lo = 42
    alpha = L.point(lambda p: 0 if p < lo else min(255, int((p - lo) * 255 / (255 - lo))))
    out = Image.new("RGBA", img.size, (244, 248, 252, 255))
    out.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox:
        out = out.crop(bbox)
    return out

mark_src = Image.open(MARK_SRC).convert("RGB")
lock_src = Image.open(LOCK_SRC).convert("RGBA")
BG = mark_src.getpixel((6, 6))  # official navy background

# 1) transparent official assets
mark_t = transparent_white(mark_src)
lock_t = transparent_white(lock_src)
mark_t.save(f"{PUB}/brand-mark.png")
lock_t.save(f"{PUB}/brand-lockup.png")

# wordmark = text block to the RIGHT of the eye+divider.
# find the widest transparent gap located in the left 40% (that's the gap after the divider).
lw, lh = lock_t.size
lpx = lock_t.load()
opaque = []
for x in range(lw):
    m = 0
    for y in range(0, lh, 3):
        a = lpx[x, y][3]
        if a > m: m = a
    opaque.append(m > 30)
# transparent runs
runs = []; s = None
for x, o in enumerate(opaque):
    if (not o) and s is None: s = x
    if o and s is not None: runs.append((s, x)); s = None
if s is not None: runs.append((s, lw))
limit = int(lw * 0.40)
cand = [(e - st, st, e) for (st, e) in runs if st < limit and (e - st) > lw * 0.01]
if cand:
    cand.sort()  # by width
    _, _, text_start = cand[-1]  # end of widest left-side gap
else:
    text_start = int(lw * 0.29)
word = lock_t.crop((text_start, 0, lw, lh))
bb = word.split()[3].getbbox()
if bb: word = word.crop(bb)
word.save(f"{PUB}/brand-wordmark.png")
print("wordmark text_start:", text_start, "-> size:", word.size)

# 2) PWA "any" icons: official navy square mark
for s in (192, 512):
    mark_src.resize((s, s), Image.LANCZOS).save(f"{PUB}/logo-mark-{s}.png")
mark_src.resize((180, 180), Image.LANCZOS).save(f"{PUB}/logo-mark-180.png")

# 3) maskable icons: full-bleed navy + centered transparent mark (52% safe zone)
def maskable(size):
    canvas = Image.new("RGBA", (size, size), BG + (255,))
    m = mark_t.copy()
    target = int(size * 0.52)
    r = target / max(m.size)
    m = m.resize((int(m.size[0] * r), int(m.size[1] * r)), Image.LANCZOS)
    canvas.alpha_composite(m, ((size - m.size[0]) // 2, (size - m.size[1]) // 2))
    canvas.convert("RGB").save(f"{PUB}/logo-maskable-{size}.png")
for s in (192, 512):
    maskable(s)

# 4) favicons (navy official mark, visible on any tab)
for s in (16, 32, 48):
    mark_src.resize((s, s), Image.LANCZOS).save(f"{PUB}/favicon-{s}.png")

# 5) iOS splash: navy bg + centered mark + OBSERRA wordmark + subtitle
def find_font():
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if os.path.exists(p):
            return p
    hits = glob.glob("/usr/share/fonts/**/*Bold*.ttf", recursive=True)
    return hits[0] if hits else None
def find_reg():
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
        if os.path.exists(p):
            return p
    hits = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    return hits[0] if hits else None
FB, FR = find_font(), find_reg()

def draw_spaced(draw, cx, y, text, font, fill, spacing):
    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=font, fill=fill)
        x += w + spacing

OUT = f"{PUB}/ios"
os.makedirs(OUT, exist_ok=True)
DEVICES = [
    (375,667,2,False),(414,736,3,False),(375,812,3,False),(414,896,2,False),(414,896,3,False),
    (390,844,3,False),(428,926,3,False),(393,852,3,False),(430,932,3,False),
    (768,1024,2,True),(810,1080,2,True),(820,1180,2,True),(834,1112,2,True),(834,1194,2,True),(1024,1366,2,True),
]

def make_splash(W, H, path):
    canvas = Image.new("RGB", (W, H), BG)
    mh = int(min(W, H) * 0.22)
    m = mark_t.copy()
    r = mh / m.size[1]
    m = m.resize((int(m.size[0] * r), mh), Image.LANCZOS)
    my = int(H / 2 - mh * 0.95)
    canvas.paste(m, ((W - m.size[0]) // 2, my), m)
    ww = int(min(W, H) * 0.52)
    wm = word.copy()
    rw = ww / wm.size[0]
    wm = wm.resize((ww, int(wm.size[1] * rw)), Image.LANCZOS)
    canvas.paste(wm, ((W - ww) // 2, my + mh + int(mh * 0.35)), wm)
    canvas.save(path)

links = []
for dw, dh, r, ipad in DEVICES:
    make_splash(dw*r, dh*r, f"{OUT}/splash-{dw}x{dh}@{r}.png")
    links.append(f'        <link rel="apple-touch-startup-image" media="screen and (device-width: {dw}px) and (device-height: {dh}px) and (-webkit-device-pixel-ratio: {r}) and (orientation: portrait)" href="%PUBLIC_URL%/ios/splash-{dw}x{dh}@{r}.png" />')
    make_splash(dh*r, dw*r, f"{OUT}/splash-{dw}x{dh}@{r}-land.png")
    links.append(f'        <link rel="apple-touch-startup-image" media="screen and (device-width: {dw}px) and (device-height: {dh}px) and (-webkit-device-pixel-ratio: {r}) and (orientation: landscape)" href="%PUBLIC_URL%/ios/splash-{dw}x{dh}@{r}-land.png" />')

open("/tmp/splash_links.html", "w").write("\n".join(links))
print("BG navy:", BG, "| font:", FB)
print("brand-mark:", mark_t.size, "brand-lockup:", lock_t.size, "| splash:", len(DEVICES), "links:", len(links))
