#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the Frutiger Aero skin images.

Wide strips are 1px GIFs tiled with background-repeat and the corner masks are
GIFs, because IE6 has no CSS gradients and no border-radius. Icons with a
non-rectangular outline are PNG-8 files with a single fully transparent palette
entry: IE6 paints alpha-channel PNGs behind a grey box, but it renders a tRNS
palette index correctly, so that is the one transparent format that works
everywhere here.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageOps

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "images")

# Frutiger Aero palette
SKY_TOP = (0x8F, 0xD4, 0xF5)
SKY_MID = (0xC9, 0xED, 0xFF)
PAGE_BG = (0xEA, 0xF6, 0xFD)
AQUA_DEEP = (0x1E, 0x6E, 0xA8)
AQUA = (0x3E, 0x9C, 0xD4)
AQUA_LT = (0x8F, 0xD1, 0xF0)
BORDER = (0x7F, 0xB9, 0xDC)
GREEN_DK = (0x3E, 0x7D, 0x14)
ORANGE = (0xE8, 0x8A, 0x1E)

SS = 4          # supersampling factor for the icons
ICON = 48       # icon edge length in CSS pixels


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def vgrad(w, h, stops):
    """Vertical multi-stop gradient. stops = [(pos0..1, (r,g,b)), ...]"""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / float(h - 1) if h > 1 else 0.0
        col = stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                col = lerp(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0.0)
                break
        for x in range(w):
            px[x, y] = col
    return img


def save_gif(img, name, colors=256, dither=False):
    if img.mode != "RGB":
        img = img.convert("RGB")
    d = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    p = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors, dither=d)
    path = os.path.join(OUT, name)
    p.save(path, "GIF", optimize=True)
    print("  %-18s %dx%d  %d bytes" % (name, img.size[0], img.size[1],
                                       os.path.getsize(path)))


def save_png8(img_rgba, name, threshold=128):
    """Palette PNG with one fully transparent index (IE6-safe transparency)."""
    alpha = img_rgba.split()[3]
    opaque = alpha.point(lambda a: 255 if a >= threshold else 0)
    rgb = img_rgba.convert("RGB")
    p = rgb.convert("P", palette=Image.Palette.ADAPTIVE, colors=255, dither=Image.Dither.NONE)
    if p.getextrema()[1] >= 255:                     # keep 255 free for the mask
        p = rgb.convert("P", palette=Image.Palette.ADAPTIVE, colors=254,
                        dither=Image.Dither.NONE)
    pal = list(p.getpalette() or [])
    while len(pal) < 256 * 3:
        pal.append(0)
    p.putpalette(pal)
    p.paste(255, ImageOps.invert(opaque))
    path = os.path.join(OUT, name)
    p.save(path, "PNG", transparency=255, optimize=True)
    print("  %-18s %dx%d  %d bytes (transparent index 255)"
          % (name, img_rgba.size[0], img_rgba.size[1], os.path.getsize(path)))


# ---------------------------------------------------------------- gloss strips
def gloss(h, stops):
    return vgrad(1, h, stops)


def build_strips():
    # brand utility bar: saturated aqua glass tube
    save_gif(gloss(30, [(0.00, (0x2A, 0x7B, 0xAE)), (0.18, (0x3E, 0x9C, 0xD4)),
                        (0.44, (0x8F, 0xD1, 0xF0)), (0.50, (0x6F, 0xC0, 0xE8)),
                        (0.86, (0x37, 0x8C, 0xC2)), (1.00, (0x27, 0x6E, 0x9E))]),
             "bar.gif")
    # panel title bar: pale aqua glass
    save_gif(gloss(26, [(0.00, (0xFF, 0xFF, 0xFF)), (0.10, (0xEC, 0xF8, 0xFF)),
                        (0.48, (0xC2, 0xE7, 0xFA)), (0.52, (0xA6, 0xDA, 0xF3)),
                        (1.00, (0x63, 0xB4, 0xE0))]), "panelhd.gif")
    # sub header: a touch deeper
    save_gif(gloss(22, [(0.00, (0xF4, 0xFC, 0xFF)), (0.45, (0xAE, 0xDD, 0xF5)),
                        (0.55, (0x8B, 0xCB, 0xEC)), (1.00, (0x5A, 0xA8, 0xD6))]),
             "subhd.gif")
    # buttons
    save_gif(gloss(23, [(0.00, (0xFF, 0xFF, 0xFF)), (0.44, (0xDD, 0xF1, 0xFC)),
                        (0.52, (0xAC, 0xDA, 0xF4)), (1.00, (0x5F, 0xAE, 0xDD))]),
             "btn.gif")
    save_gif(gloss(23, [(0.00, (0xFF, 0xFF, 0xFF)), (0.44, (0xEE, 0xFA, 0xFF)),
                        (0.52, (0xC6, 0xEC, 0xFF)), (1.00, (0x3E, 0x9B, 0xD8))]),
             "btn_on.gif")
    # primary download button: aero green
    save_gif(gloss(25, [(0.00, (0xF4, 0xFF, 0xE2)), (0.42, (0xCE, 0xF0, 0x96)),
                        (0.52, (0x9B, 0xD8, 0x4E)), (1.00, (0x4E, 0x9E, 0x18))]),
             "btn_dl.gif")
    save_gif(gloss(25, [(0.00, (0xFF, 0xFF, 0xEE)), (0.42, (0xE4, 0xFA, 0xBC)),
                        (0.52, (0xB6, 0xE8, 0x6A)), (1.00, (0x3E, 0x88, 0x10))]),
             "btn_dl_on.gif")
    # selected nav row
    save_gif(gloss(26, [(0.00, (0xFF, 0xFF, 0xFF)), (0.46, (0xC8, 0xEA, 0xFB)),
                        (0.54, (0x9E, 0xD6, 0xF2)), (1.00, (0x6F, 0xB8, 0xE2))]),
             "navsel.gif")
    # "new" badge
    save_gif(gloss(15, [(0.00, (0xFF, 0xE9, 0xC2)), (0.45, (0xF7, 0xC0, 0x60)),
                        (0.55, (0xEE, 0x9B, 0x2A)), (1.00, (0xC9, 0x6A, 0x08))]),
             "badge.gif")
    # status footer: eco green glass
    save_gif(gloss(30, [(0.00, (0xE4, 0xF8, 0xC6)), (0.40, (0xAE, 0xE2, 0x6C)),
                        (0.52, (0x84, 0xCB, 0x36)), (1.00, (0x3E, 0x7D, 0x14))]),
             "footer.gif")

    # ---- mobile: same skin, taller strips -------------------------------
    # A repeat-x strip only covers the first N pixels vertically; anything
    # below falls back to the flat background colour, so touch-sized controls
    # need their own taller gradients rather than a stretched 23px one.
    save_gif(gloss(48, [(0.00, (0x2A, 0x7B, 0xAE)), (0.14, (0x3E, 0x9C, 0xD4)),
                        (0.42, (0x8F, 0xD1, 0xF0)), (0.50, (0x6F, 0xC0, 0xE8)),
                        (0.86, (0x37, 0x8C, 0xC2)), (1.00, (0x27, 0x6E, 0x9E))]),
             "m_bar.gif")
    save_gif(gloss(30, [(0.00, (0xFF, 0xFF, 0xFF)), (0.10, (0xEC, 0xF8, 0xFF)),
                        (0.48, (0xC2, 0xE7, 0xFA)), (0.52, (0xA6, 0xDA, 0xF3)),
                        (1.00, (0x63, 0xB4, 0xE0))]), "m_hd.gif")
    save_gif(gloss(34, [(0.00, (0xFF, 0xFF, 0xFF)), (0.44, (0xDD, 0xF1, 0xFC)),
                        (0.52, (0xAC, 0xDA, 0xF4)), (1.00, (0x5F, 0xAE, 0xDD))]),
             "m_btn.gif")
    save_gif(gloss(34, [(0.00, (0xFF, 0xFF, 0xFF)), (0.44, (0xEE, 0xFA, 0xFF)),
                        (0.52, (0xC6, 0xEC, 0xFF)), (1.00, (0x3E, 0x9B, 0xD8))]),
             "m_btn_on.gif")
    save_gif(gloss(38, [(0.00, (0xF4, 0xFF, 0xE2)), (0.42, (0xCE, 0xF0, 0x96)),
                        (0.52, (0x9B, 0xD8, 0x4E)), (1.00, (0x4E, 0x9E, 0x18))]),
             "m_dl.gif")
    save_gif(gloss(38, [(0.00, (0xFF, 0xFF, 0xEE)), (0.42, (0xE4, 0xFA, 0xBC)),
                        (0.52, (0xB6, 0xE8, 0x6A)), (1.00, (0x3E, 0x88, 0x10))]),
             "m_dl_on.gif")


# ------------------------------------------------------------------- sky band
HERO_H = 116
SKY_STOPS = [(0.00, (0x74, 0xC6, 0xEE)), (0.20, (0x9A, 0xDA, 0xF6)),
             (0.52, (0xC6, 0xEC, 0xFF)), (0.78, (0xE0, 0xF5, 0xFF)),
             (1.00, PAGE_BG)]


def build_hero():
    save_gif(vgrad(1, HERO_H, SKY_STOPS), "hero_bg.gif")


def soft_disc(mask, cx, cy, r, peak, inner=0.0):
    """Accumulate a soft round blob into an 'L' mask (max blend)."""
    px = mask.load()
    w, h = mask.size
    for y in range(max(0, int(cy - r)), min(h, int(cy + r) + 1)):
        for x in range(max(0, int(cx - r)), min(w, int(cx + r) + 1)):
            d = math.hypot(x - cx, y - cy) / r
            if d > 1.0:
                continue
            a = peak * (1.0 - d * d) ** 0.5 if inner == 0 else peak * (1.0 - d) ** inner
            if a > px[x, y]:
                px[x, y] = int(min(255, a))


def soft_ring(mask, cx, cy, r, width, peak):
    px = mask.load()
    w, h = mask.size
    for y in range(max(0, int(cy - r - width * 2)), min(h, int(cy + r + width * 2) + 1)):
        for x in range(max(0, int(cx - r - width * 2)), min(w, int(cx + r + width * 2) + 1)):
            d = math.hypot(x - cx, y - cy)
            a = peak * math.exp(-((d - r) ** 2) / (2.0 * (width / 1.6) ** 2))
            if a > px[x, y]:
                px[x, y] = int(min(255, a))


def build_hero_art():
    """Opaque art tile carrying the exact same vertical gradient, so it blends
    seamlessly into the hero band without needing alpha."""
    w, h = 470, HERO_H
    base = vgrad(w, h, SKY_STOPS).convert("RGB")
    light = Image.new("L", (w, h), 0)
    tint = Image.new("L", (w, h), 0)

    bubbles = [(0.30, 0.42, 26), (0.55, 0.24, 15), (0.70, 0.62, 34),
               (0.86, 0.30, 12), (0.44, 0.74, 18), (0.93, 0.70, 20),
               (0.16, 0.70, 11)]
    for fx, fy, r in bubbles:
        cx, cy = fx * w, fy * h
        soft_disc(tint, cx, cy, r * 1.05, 84, inner=1.2)
        soft_ring(light, cx, cy, r * 0.94, r * 0.28, 220)
        soft_disc(light, cx - r * 0.34, cy - r * 0.40, r * 0.30, 235)
        soft_disc(light, cx + r * 0.36, cy + r * 0.42, r * 0.17, 110)

    # glassy sweep across the upper third; the left edge fades out so the tile
    # still tiles seamlessly against the plain gradient strip
    sweep = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(sweep)
    d.polygon([(0, 0), (w, 0), (w, int(h * 0.30)), (0, int(h * 0.52))], fill=90)
    sweep = sweep.filter(ImageFilter.GaussianBlur(6))
    ramp = Image.new("L", (w, 1))
    rp = ramp.load()
    for x in range(w):
        rp[x, 0] = int(255 * min(1.0, x / 90.0))
    sweep = Image.composite(sweep, Image.new("L", (w, h), 0), ramp.resize((w, h)))

    base = Image.composite(Image.new("RGB", (w, h), (0xFF, 0xFF, 0xFF)), base,
                           sweep.point(lambda v: int(v * 0.55)))
    base = Image.composite(Image.new("RGB", (w, h), (0xFF, 0xFF, 0xFF)), base, light)
    base = Image.composite(Image.new("RGB", (w, h), (0x5A, 0xB4, 0xE0)), base,
                           tint.point(lambda v: int(v * 0.5)))
    save_gif(base, "hero_art.gif", colors=256, dither=True)


# -------------------------------------------------------------------- corners
CN = 9
RAD = 8.0


def corner(flip_x, flip_y, name):
    img = Image.new("RGB", (CN, CN), PAGE_BG)
    px = img.load()
    for y in range(CN):
        for x in range(CN):
            sx = (CN - 1 - x) if flip_x else x
            sy = (CN - 1 - y) if flip_y else y
            fx, fy = sx + 0.5, sy + 0.5
            d = math.hypot(max(RAD - fx, 0.0), max(RAD - fy, 0.0)) - RAD
            if d > 0:
                px[x, y] = PAGE_BG
            elif d > -1.0:
                px[x, y] = BORDER
            else:
                px[x, y] = (0xFF, 0xFF, 0xFF)
    save_gif(img, name, colors=8)


def build_corners():
    corner(False, False, "cn_tl.gif")
    corner(True, False, "cn_tr.gif")
    corner(False, True, "cn_bl.gif")
    corner(True, True, "cn_br.gif")


# ---------------------------------------------------------------- tiny glyphs
def build_glyphs():
    img = Image.new("RGB", (9, 9), PAGE_BG)
    d = ImageDraw.Draw(img)
    d.polygon([(4, 0), (8, 4), (4, 8), (0, 4)], fill=AQUA_DEEP)
    d.polygon([(4, 1), (7, 4), (4, 7), (1, 4)], fill=AQUA_LT)
    save_gif(img, "bullet.gif", colors=8)

    for name, col in (("dot_on.gif", (0x53, 0xC8, 0x22)), ("dot_off.gif", (0xB4, 0xC3, 0xCC))):
        img = Image.new("RGB", (11, 11), PAGE_BG)
        d = ImageDraw.Draw(img)
        d.ellipse([1, 1, 9, 9], fill=lerp(col, (0, 0, 0), 0.35))
        d.ellipse([2, 2, 8, 8], fill=col)
        d.ellipse([3, 2, 6, 5], fill=(0xFF, 0xFF, 0xFF))
        save_gif(img, name, colors=16)


# ------------------------------------------------------------- logo and tiles
def render_sphere(size=ICON, ss=SS, ground=False, arrow=True):
    """Glossy Frutiger Aero sphere, rendered supersampled.

    Returns (rgb, coverage): the colour layer has the rim colour bled past the
    silhouette so that downsampling never mixes transparent black into the
    edge, and coverage is a clean anti-aliased circle mask.
    """
    n = size * ss
    rgb = Image.new("RGB", (n, n), (0xF2, 0xFB, 0xFF))
    cov = Image.new("L", (n, n), 0)
    rp, cp = rgb.load(), cov.load()
    cx = cy = n / 2.0
    R = n / 2.0 - 1.2 * ss

    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if d <= R:
                cp[x, y] = 255
            r = min(1.0, d / R)
            lit = (dx + dy) / (2.0 * R)                 # -1 upper-left, +1 lower-right
            t = min(1.0, max(0.0, 0.26 + r * 0.66 + lit * 0.46))
            col = lerp((0xD6, 0xF2, 0xFF), (0x14, 0x5C, 0x92), t)
            if ground and dy > R * (0.22 + 0.14 * (dy / R)):
                g = lerp((0xA8, 0xE0, 0x62), (0x3E, 0x7D, 0x14),
                         min(1.0, (dy - R * 0.22) / (R * 0.8)))
                col = lerp(col, g, 0.90)
            if d > R:
                col = lerp(col, (0xF2, 0xFB, 0xFF), 0.70)   # silhouette bleed
            rp[x, y] = col

    # Edge treatment. The icon ships as a palette PNG with on/off
    # transparency, so the silhouette is a hard cut: a hairline of near-sky
    # colour outside a crisp inner line keeps the shape readable while the
    # stair steps land in the low-contrast fringe instead of on a dark rim.
    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if d > R:
                continue
            e = (R - d) / ss                            # distance inside the edge, CSS px
            top = max(0.0, -dy / R)                     # 1 at the top, 0 at the bottom
            if e < 0.65:
                rp[x, y] = lerp(rp[x, y], (0xEC, 0xF9, 0xFF), 0.80)
            elif e < 1.6:
                rp[x, y] = lerp(rp[x, y], (0x0E, 0x46, 0x74), 0.70)
            elif e < 2.6:
                rp[x, y] = lerp(rp[x, y], (0xFF, 0xFF, 0xFF), 0.22 + 0.48 * top)

    # specular highlight and a soft bottom bounce light
    hl = Image.new("L", (n, n), 0)
    soft_disc(hl, cx - R * 0.32, cy - R * 0.46, R * 0.46, 236)
    soft_disc(hl, cx + R * 0.34, cy + R * 0.50, R * 0.30, 96)
    rgb = Image.composite(Image.new("RGB", (n, n), (0xFF, 0xFF, 0xFF)), rgb, hl)

    if arrow:
        shape = Image.new("L", (n, n), 0)
        d = ImageDraw.Draw(shape)
        w, t = 3.0 * ss, 12.0 * ss                      # shaft half-width, head half-width
        d.rectangle([cx - w, 11.5 * ss, cx + w, 26.0 * ss], fill=255)
        d.polygon([(cx - t, 24.0 * ss), (cx + t, 24.0 * ss), (cx, 37.5 * ss)], fill=255)
        shadow = Image.new("L", (n, n), 0)
        shadow.paste(shape, (0, int(1.4 * ss)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(1.1 * ss))
        rgb = Image.composite(Image.new("RGB", (n, n), (0x10, 0x40, 0x66)), rgb,
                              shadow.point(lambda v: int(v * 0.42)))
        rgb = Image.composite(Image.new("RGB", (n, n), (0xFF, 0xFF, 0xFF)), rgb, shape)

    rgbs = rgb.resize((size, size), Image.LANCZOS)
    covs = cov.resize((size, size), Image.LANCZOS)
    out = rgbs.convert("RGBA")
    out.putalpha(covs)
    return out


def build_logo():
    icon = render_sphere(ground=False, arrow=True)
    save_png8(icon, "logo.png")
    # favicon keeps the real alpha channel: .ico is not affected by the IE6
    # alpha-PNG limitation and browsers render it with smooth edges
    icon.save(os.path.join(OUT, "..", "favicon.ico"), sizes=[(16, 16), (32, 32)])
    print("  favicon.ico        16x16 + 32x32 (alpha)")


def render_tile(size=ICON, ss=SS, radius_ratio=0.30):
    """Glossy rounded square used behind the per-app initial letters."""
    n = size * ss
    rgb = Image.new("RGB", (n, n), (0xD8, 0xF1, 0xFF))
    cov = Image.new("L", (n, n), 0)
    rp, cp = rgb.load(), cov.load()
    r = radius_ratio * n
    for y in range(n):
        for x in range(n):
            fx, fy = x + 0.5, y + 0.5
            d = math.hypot(max(r - fx, 0.0), max(r - fy, 0.0)) - r
            if d <= 0:
                cp[x, y] = 255
            t = y / float(n - 1)
            col = lerp((0xCF, 0xEE, 0xFF), (0x3E, 0x9C, 0xD4),
                       t / 0.5 if t < 0.5 else 1.0 - (t - 0.5) * 0.30)
            if d <= 0 and d > -1.6 * ss:
                col = lerp(col, (0x14, 0x5C, 0x92), 0.72)
            rp[x, y] = col if d <= 0 else lerp(col, (0xCF, 0xEC, 0xFF), 0.62)
    gloss = Image.new("L", (n, n), 0)
    ImageDraw.Draw(gloss).polygon([(0, 0), (n, 0), (n, n * 0.34), (0, n * 0.54)], fill=118)
    gloss = gloss.filter(ImageFilter.GaussianBlur(2.0 * ss))
    rgb = Image.composite(Image.new("RGB", (n, n), (0xFF, 0xFF, 0xFF)), rgb, gloss)
    rgbs = rgb.resize((size, size), Image.LANCZOS)
    covs = cov.resize((size, size), Image.LANCZOS)
    out = rgbs.convert("RGBA")
    out.putalpha(covs)
    return out


def build_tiles():
    save_png8(render_tile(), "tile.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    print("skin assets -> %s" % os.path.normpath(OUT))
    for stale in ("logo.gif", "tile.gif", "tile_s.gif", "arrow.gif"):
        p = os.path.join(OUT, stale)
        if os.path.exists(p):
            os.remove(p)
            print("  removed superseded %s" % stale)
    build_strips()
    build_hero()
    build_hero_art()
    build_corners()
    build_glyphs()
    build_logo()
    build_tiles()
    print("done")


if __name__ == "__main__":
    main()
