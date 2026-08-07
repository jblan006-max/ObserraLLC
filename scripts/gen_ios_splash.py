import cairosvg, os
PUB = "/app/frontend/public"
OUT = os.path.join(PUB, "ios")
os.makedirs(OUT, exist_ok=True)

MARK = '''
  <path d="M35 128c25-37 55-56 93-56s68 19 93 56c-25 37-55 56-93 56s-68-19-93-56Z" fill="none" stroke="#F4F8FC" stroke-width="13" stroke-linejoin="round"/>
  <circle cx="128" cy="128" r="40" fill="none" stroke="#F4F8FC" stroke-width="9"/>
  <circle cx="128" cy="115" r="13" fill="#F4F8FC"/>
  <path d="M119 123 L137 123 L143 153 L113 153 Z" fill="#F4F8FC"/>
'''

def splash_svg(W, H):
    mark = min(W, H) * 0.26
    s = mark / 256.0
    tx = (W - mark) / 2.0
    ty = (H - mark) / 2.0 - H * 0.045
    fs = mark * 0.15
    ls = fs * 0.35
    subfs = fs * 0.34
    ty_text = ty + mark + fs * 1.5
    ty_sub = ty_text + subfs * 2.4
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="#061F3B"/>
  <g transform="translate({tx},{ty}) scale({s})">{MARK}</g>
  <text x="{W/2}" y="{ty_text}" text-anchor="middle" fill="#F4F8FC" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="{fs}" letter-spacing="{ls}">OBSERRA</text>
  <text x="{W/2}" y="{ty_sub}" text-anchor="middle" fill="#8AA0B8" font-family="Arial, Helvetica, sans-serif" font-size="{subfs}" letter-spacing="{subfs*0.18}">EXECUTIVE PROTECTION &amp; INTELLIGENCE LLC</text>
</svg>'''

# (device_width, device_height, ratio, is_ipad)
DEVICES = [
    (375,667,2,False),(414,736,3,False),(375,812,3,False),(414,896,2,False),(414,896,3,False),
    (390,844,3,False),(428,926,3,False),(393,852,3,False),(430,932,3,False),
    (768,1024,2,True),(810,1080,2,True),(820,1180,2,True),(834,1112,2,True),(834,1194,2,True),(1024,1366,2,True),
]

links = []
for dw, dh, r, ipad in DEVICES:
    # portrait
    W, H = dw*r, dh*r
    fp = f"splash-{dw}x{dh}@{r}.png"
    cairosvg.svg2png(bytestring=splash_svg(W, H).encode(), write_to=os.path.join(OUT, fp), output_width=W, output_height=H)
    links.append(f'        <link rel="apple-touch-startup-image" media="screen and (device-width: {dw}px) and (device-height: {dh}px) and (-webkit-device-pixel-ratio: {r}) and (orientation: portrait)" href="%PUBLIC_URL%/ios/{fp}" />')
    if ipad:
        # landscape (swap dimensions)
        LW, LH = dh*r, dw*r
        fl = f"splash-{dw}x{dh}@{r}-land.png"
        cairosvg.svg2png(bytestring=splash_svg(LW, LH).encode(), write_to=os.path.join(OUT, fl), output_width=LW, output_height=LH)
        links.append(f'        <link rel="apple-touch-startup-image" media="screen and (device-width: {dw}px) and (device-height: {dh}px) and (-webkit-device-pixel-ratio: {r}) and (orientation: landscape)" href="%PUBLIC_URL%/ios/{fl}" />')

with open("/tmp/splash_links.html", "w") as f:
    f.write("\n".join(links))

# maskable icons: full-bleed navy, mark ~52% centered inside safe zone
def maskable_svg(size):
    mark = size * 0.52
    s = mark / 256.0
    off = (size - mark) / 2.0
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="#061F3B"/>
  <g transform="translate({off},{off}) scale({s})">{MARK}</g>
</svg>'''

for sz in (192, 512):
    cairosvg.svg2png(bytestring=maskable_svg(sz).encode(), write_to=os.path.join(PUB, f"logo-maskable-{sz}.png"), output_width=sz, output_height=sz)

print("splash links:", len(links), "| maskable icons: 192,512")
