import cairosvg, os
OUT = "/app/frontend/public/ios"
os.makedirs(OUT, exist_ok=True)

MARK = '''
  <path d="M35 128c25-37 55-56 93-56s68 19 93 56c-25 37-55 56-93 56s-68-19-93-56Z" fill="none" stroke="#F4F8FC" stroke-width="13" stroke-linejoin="round"/>
  <circle cx="128" cy="128" r="40" fill="none" stroke="#F4F8FC" stroke-width="9"/>
  <circle cx="128" cy="115" r="13" fill="#F4F8FC"/>
  <path d="M119 123 L137 123 L143 153 L113 153 Z" fill="#F4F8FC"/>
'''

# (device_width, device_height, ratio) portrait
DEVICES = [
    (375,667,2),(414,736,3),(375,812,3),(414,896,2),(414,896,3),
    (390,844,3),(428,926,3),(393,852,3),(430,932,3),
    (768,1024,2),(810,1080,2),(820,1180,2),(834,1112,2),(834,1194,2),(1024,1366,2),
]

links = []
for dw, dh, r in DEVICES:
    W, H = dw*r, dh*r
    mark = min(W, H) * 0.26
    s = mark / 256.0
    tx = (W - mark) / 2.0
    ty = (H - mark) / 2.0 - H * 0.045
    fs = mark * 0.15
    ls = fs * 0.35
    subfs = fs * 0.34
    ty_text = ty + mark + fs * 1.5
    ty_sub = ty_text + subfs * 2.4
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="#061F3B"/>
  <g transform="translate({tx},{ty}) scale({s})">{MARK}</g>
  <text x="{W/2}" y="{ty_text}" text-anchor="middle" fill="#F4F8FC" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="{fs}" letter-spacing="{ls}">OBSERRA</text>
  <text x="{W/2}" y="{ty_sub}" text-anchor="middle" fill="#8AA0B8" font-family="Arial, Helvetica, sans-serif" font-size="{subfs}" letter-spacing="{subfs*0.18}">EXECUTIVE PROTECTION &amp; INTELLIGENCE LLC</text>
</svg>'''
    fname = f"splash-{dw}x{dh}@{r}.png"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(OUT, fname), output_width=W, output_height=H)
    media = (f"screen and (device-width: {dw}px) and (device-height: {dh}px) "
             f"and (-webkit-device-pixel-ratio: {r}) and (orientation: portrait)")
    links.append(f'        <link rel="apple-touch-startup-image" media="{media}" href="%PUBLIC_URL%/ios/{fname}" />')

with open("/tmp/splash_links.html", "w") as f:
    f.write("\n".join(links))
print(f"generated {len(DEVICES)} splash images")
print("\n".join(links[:2]))
