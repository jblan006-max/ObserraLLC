// White-label: convert a hex accent into an HSL triplet and restyle the app chrome live.
export function hexToHslTriplet(hex) {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let hue = 0, sat = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) hue = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) hue = (b - r) / d + 2;
    else hue = (r - g) / d + 4;
    hue /= 6;
  }
  return `${Math.round(hue * 360)} ${Math.round(sat * 100)}% ${Math.round(l * 100)}%`;
}

export function applyBranding(data) {
  if (!data) return;
  if (data.display_name) document.title = data.display_name;
  if (data.accent) {
    const t = hexToHslTriplet(data.accent);
    const root = document.documentElement.style;
    root.setProperty("--brand-accent", data.accent);
    root.setProperty("--primary", t);
    root.setProperty("--ai", t);
    root.setProperty("--ring", t);
  }
}
