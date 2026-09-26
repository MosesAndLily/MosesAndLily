"""Generate the profile banner (light + dark) and the link buttons.

Text is shaped with HarfBuzz and converted to SVG outlines, so no fonts are needed at view time.
The whip in the banner is a two-link arm plus a bead chain simulated with position-based dynamics.
By default one still frame of the cast is drawn; set ANIMATE = True to bake the whole motion into SMIL keyframes.
"""
import math
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
OUT = HERE.parent

# Palette: MosesAndLily.github.io/styles/tokens-{light,dark}.scss
THEMES = {
    "light": dict(ink="#1b2130", ink2="#3a4152", muted="#5f6776", accent="#1e4fa3", target="#c9c7c0",
                  btn_bg="#1e4fa3", btn_fg="#ffffff"),
    "dark": dict(ink="#e8e6df", ink2="#c9c7c0", muted="#9aa2b1", accent="#8db1ff", target="#3a4152",
                 btn_bg="#8db1ff", btn_fg="#0e1117"),
}


def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


class Face:
    """A font face at fixed variable-axis coordinates, able to turn text into an SVG path."""

    def __init__(self, path, variations=None):
        self.font = hb.Font(hb.Face(Path(path).read_bytes()))
        self.upem = self.font.face.upem
        self.font.scale = (self.upem, self.upem)
        if variations:
            self.font.set_variations(variations)

    def path(self, text, x, y, size, tracking=0.0):
        """Return (path data, advance width) for `text` with its baseline at (x, y)."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf)
        s = size / self.upem
        cx, cmds = x, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            rec = RecordingPen()
            self.font.draw_glyph_with_pen(info.codepoint, rec)
            pen = SVGPathPen(None, ntos=num)
            rec.replay(TransformPen(pen, (s, 0, 0, -s, cx + pos.x_offset * s, y - pos.y_offset * s)))
            if pen.getCommands():
                cmds.append(pen.getCommands())
            cx += pos.x_advance * s + tracking
        return " ".join(cmds), cx - x - tracking


# ----------------------------------------------------------------------------- whip simulation
def minjerk(s):
    s = min(max(s, 0.0), 1.0)
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def lerp(a, b, s):
    return a + (b - a) * s


def arm_angles(t, keys):
    """keys: (start time, duration, upper-arm angle, forearm angle); each pose is reached by a min-jerk move."""
    a1, a2 = keys[0][2], keys[0][3]
    for t0, dur, k1, k2 in keys[1:]:
        if t >= t0:
            s = minjerk((t - t0) / dur) if dur > 0 else 1.0
            a1, a2 = lerp(a1, k1, s), lerp(a2, k2, s)
    return math.radians(a1), math.radians(a2)


def simulate(shoulder, L1, L2, keys, N, seg, T, fps, g=1400.0, damp=0.9965, sub=12, iters=24):
    """Verlet-integrated bead chain hanging from the hand of a two-link arm. Returns per-frame
    (elbow, hand, [bead positions])."""

    def hand(t):
        a1, a2 = arm_angles(t, keys)
        e = (shoulder[0] + L1 * math.cos(a1), shoulder[1] + L1 * math.sin(a1))
        return e, (e[0] + L2 * math.cos(a2), e[1] + L2 * math.sin(a2))

    _, h0 = hand(0.0)
    p = [[h0[0], h0[1] + seg * i] for i in range(N)]
    prev = [q[:] for q in p]
    dt = 1.0 / (fps * sub)
    frames, nF = [], int(T * fps)
    for f in range(nF):
        for k in range(sub):
            e, h = hand((f + k / sub) / fps)
            p[0] = [h[0], h[1]]
            for i in range(1, N):
                vx = (p[i][0] - prev[i][0]) * damp
                vy = (p[i][1] - prev[i][1]) * damp
                prev[i] = p[i][:]
                p[i] = [p[i][0] + vx, p[i][1] + vy + g * dt * dt]
            for _ in range(iters):
                p[0] = [h[0], h[1]]
                for i in range(N - 1):
                    dx, dy = p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]
                    d = math.hypot(dx, dy) or 1e-9
                    cx, cy = (d - seg) / d * dx, (d - seg) / d * dy
                    if i == 0:
                        p[1][0] -= cx
                        p[1][1] -= cy
                    else:
                        p[i][0] += 0.5 * cx
                        p[i][1] += 0.5 * cy
                        p[i + 1][0] -= 0.5 * cx
                        p[i + 1][1] -= 0.5 * cy
        e, h = hand(f / fps)
        frames.append((e, h, [q[:] for q in p]))
    # Blend the last 0.6 s toward frame 0 so the loop closes without a jump.
    nb = int(0.6 * fps)
    for j in range(nb):
        s, f = minjerk((j + 1) / nb), nF - nb + j
        e0, h0, p0 = frames[0]
        e, h, pp = frames[f]
        frames[f] = (
            (lerp(e[0], e0[0], s), lerp(e[1], e0[1], s)),
            (lerp(h[0], h0[0], s), lerp(h[1], h0[1], s)),
            [[lerp(a[0], b[0], s), lerp(a[1], b[1], s)] for a, b in zip(pp, p0)],
        )
    return frames


def hexlerp(a, b, s):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * s) for i in range(3))


# ----------------------------------------------------------------------------- banner
W, H = 1200, 340


ANIMATE = False  # False: one still frame of the cast. True: bake the whole motion into SMIL keyframes.


def banner(theme, faces, frames, fps, T, shoulder, target, hit_f, N):
    c = THEMES[theme]
    news, sans, sansb, kr = faces
    x0 = 64
    eyebrow, _ = sansb.path("ROBOTICS · CONTROL · PHYSICAL INTERACTION", x0, 108, 14.5, tracking=2.6)
    name, name_w = news.path("Moses C. Nah", x0, 186, 78)
    krname, _ = kr.path("나종욱 · 羅鍾煜", x0 + name_w + 26, 184, 27)
    desc, _ = sans.path("Holiday Robotics Research Inc.  ·  Ph.D. in Mechanical Engineering, MIT", x0, 232, 21)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        'aria-label="Moses C. Nah. Robotics, control, physical interaction. '
        'Holiday Robotics Research Inc.; Ph.D. in Mechanical Engineering, MIT.">',
        f'<path fill="{c["accent"]}" d="{eyebrow}"/>',
        f'<path fill="{c["ink"]}" d="{name}"/>',
        f'<path fill="{c["muted"]}" d="{krname}"/>',
        f'<path fill="{c["ink2"]}" d="{desc}"/>',
        f'<line x1="{x0}" y1="266" x2="{x0 + 120}" y2="266" stroke="{c["accent"]}" stroke-width="2"/>',
    ]
    tx, ty, tr = target
    sx, sy = shoulder
    arm = f'stroke="{c["ink"]}" stroke-width="5.5" stroke-linecap="round"'

    if not ANIMATE:
        # A single still: the instant the whip tip reaches the target.
        e, h, beads = frames[hit_f]
        out.append(f'<circle cx="{tx}" cy="{ty}" r="{tr}" fill="{c["accent"]}"/>')
        out.append(f'<circle cx="{tx}" cy="{ty}" r="{tr + 7}" fill="none" stroke="{c["accent"]}" stroke-width="1.5" opacity="0.45"/>')
        out.append(f'<line x1="{sx}" y1="{sy}" x2="{e[0]:.1f}" y2="{e[1]:.1f}" {arm}/>')
        out.append(f'<line x1="{e[0]:.1f}" y1="{e[1]:.1f}" x2="{h[0]:.1f}" y2="{h[1]:.1f}" {arm}/>')
        out.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{c["ink"]}"/>')
        for i in range(1, N):
            s = (i - 1) / (N - 2)
            out.append(f'<circle cx="{beads[i][0]:.1f}" cy="{beads[i][1]:.1f}" r="{3.6 - 1.2 * s:.1f}" '
                       f'fill="{hexlerp(c["ink2"], c["accent"], s)}"/>')
        out.append("</svg>")
        return "\n".join(out)

    dur = f"{T}s"

    def anim(attr, vals):
        return (f'<animate attributeName="{attr}" dur="{dur}" repeatCount="indefinite" '
                f'values="{";".join(("%.1f" % v).rstrip("0").rstrip(".") for v in vals)}"/>')

    # Target: flashes and sends out a ring when the whip tip arrives.
    th = hit_f / fps / T
    t1, t2, t3, t4 = f"{th:.4f}", f"{th + 0.03:.4f}", f"{th + 0.16:.4f}", f"{th + 0.40:.4f}"
    out.append(
        f'<circle cx="{tx}" cy="{ty}" r="{tr}" fill="{c["target"]}"><animate attributeName="fill" dur="{dur}" '
        f'repeatCount="indefinite" calcMode="discrete" keyTimes="0;{t1};{t4};1" '
        f'values="{c["target"]};{c["accent"]};{c["target"]};{c["target"]}"/></circle>')
    out.append(
        f'<circle cx="{tx}" cy="{ty}" r="{tr}" fill="none" stroke="{c["accent"]}" stroke-width="2" opacity="0">'
        f'<animate attributeName="r" dur="{dur}" repeatCount="indefinite" keyTimes="0;{t1};{t3};1" '
        f'values="{tr};{tr};{tr + 30};{tr + 30}"/>'
        f'<animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" keyTimes="0;{t1};{t2};{t3};1" '
        f'values="0;0;0.9;0;0"/></circle>')
    # Two-link arm.
    ex = [f[0][0] for f in frames]; ey = [f[0][1] for f in frames]
    hx = [f[1][0] for f in frames]; hy = [f[1][1] for f in frames]
    out.append(f'<line x1="{sx}" y1="{sy}" x2="{ex[0]:.1f}" y2="{ey[0]:.1f}" {arm}>{anim("x2", ex)}{anim("y2", ey)}</line>')
    out.append(f'<line x1="{ex[0]:.1f}" y1="{ey[0]:.1f}" x2="{hx[0]:.1f}" y2="{hy[0]:.1f}" {arm}>'
               f'{anim("x1", ex)}{anim("y1", ey)}{anim("x2", hx)}{anim("y2", hy)}</line>')
    out.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{c["ink"]}"/>')
    # Bead chain, shading from ink to accent toward the tip.
    for i in range(1, N):
        s = (i - 1) / (N - 2)
        xs = [f[2][i][0] for f in frames]; ys = [f[2][i][1] for f in frames]
        out.append(f'<circle cx="{xs[0]:.1f}" cy="{ys[0]:.1f}" r="{3.6 - 1.2 * s:.1f}" '
                   f'fill="{hexlerp(c["ink2"], c["accent"], s)}">{anim("cx", xs)}{anim("cy", ys)}</circle>')
    out.append("</svg>")
    return "\n".join(out)


# ----------------------------------------------------------------------------- buttons
BTN_H, BTN_R, PAD_L, GAP, PAD_R, ICON, FS = 32, 16, 13, 8, 15, 15, 13.5


def icon(kind, fg, sansb):
    s = f'stroke="{fg}" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "website":
        return (f'<circle cx="8" cy="8" r="6.4" {s}/><ellipse cx="8" cy="8" rx="2.7" ry="6.4" {s}/>'
                f'<line x1="1.6" y1="8" x2="14.4" y2="8" {s}/><path d="M2.6 4.6 Q8 6.6 13.4 4.6 M2.6 11.4 Q8 9.4 13.4 11.4" {s}/>')
    if kind == "scholar":
        return (f'<path d="M8 2.6 L15 6.1 L8 9.6 L1 6.1 Z" fill="{fg}"/>'
                f'<path d="M4.3 8 v3.1 c0 1.3 7.4 1.3 7.4 0 V8" {s}/><line x1="14.2" y1="6.6" x2="14.2" y2="10.6" {s}/>')
    if kind == "orcid":
        d, w = sansb.path("iD", 0, 0, 8.4)
        return f'<circle cx="8" cy="8" r="6.6" {s}/><path fill="{fg}" transform="translate({8 - w / 2:.2f},11)" d="{d}"/>'
    if kind == "linkedin":
        d, w = sansb.path("in", 0, 0, 16.5)
        return f'<path fill="{fg}" transform="translate({8 - w / 2:.2f},13.6)" d="{d}"/>'
    if kind == "email":
        return f'<rect x="1.6" y="3.4" width="12.8" height="9.2" rx="1.6" {s}/><path d="M1.9 4.4 L8 9.1 L14.1 4.4" {s}/>'
    if kind == "cv":
        return (f'<path d="M3.2 1.8 h6.3 l3.3 3.3 v9.1 h-9.6 Z" {s}/><path d="M9.5 1.8 v3.3 h3.3" {s}/>'
                f'<line x1="5.4" y1="8" x2="10.6" y2="8" {s}/><line x1="5.4" y1="10.6" x2="10.6" y2="10.6" {s}/>')
    raise ValueError(kind)


def button(kind, label, theme, sansb):
    c = THEMES[theme]
    d, w = sansb.path(label, 0, 0, FS, tracking=0.25)
    total = round(PAD_L + ICON + GAP + w + PAD_R)
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{BTN_H}" viewBox="0 0 {total} {BTN_H}" role="img" aria-label="{label}">',
        f'<rect width="{total}" height="{BTN_H}" rx="{BTN_R}" fill="{c["btn_bg"]}"/>',
        f'<g transform="translate({PAD_L},{(BTN_H - 16) / 2})">{icon(kind, c["btn_fg"], sansb)}</g>',
        f'<path fill="{c["btn_fg"]}" transform="translate({PAD_L + ICON + GAP:.2f},{BTN_H / 2 + 4.7:.2f})" d="{d}"/>',
        "</svg>",
    ])


# ----------------------------------------------------------------------------- main
def main():
    faces = (
        Face(FONTS / "Newsreader-VF.ttf", {"wght": 500, "opsz": 72}),
        Face(FONTS / "SourceSans3-VF.ttf", {"wght": 400}),
        Face(FONTS / "SourceSans3-VF.ttf", {"wght": 600}),
        Face(FONTS / "NotoSerifKR-VF.ttf", {"wght": 500}),
    )
    fps, T, N, seg = 20, 6.0, 16, 6.6
    shoulder, L1, L2 = (952, 112), 40, 40
    # Angles in degrees: 0 = right, 90 = down. One min-jerk cast, a hold, then a slow return.
    keys = [(0.0, 0, 96, 84), (0.8, 0.72, -14, 12), (3.5, 1.25, 96, 84)]
    frames = simulate(shoulder, L1, L2, keys, N, seg, T, fps)
    hit_f = max(range(int(1.0 * fps), int(3.2 * fps)), key=lambda f: frames[f][2][-1][0])
    tip = frames[hit_f][2][-1]
    target = (round(tip[0], 1), round(tip[1], 1), 8)
    for theme in THEMES:
        svg = banner(theme, faces, frames, fps, T, shoulder, target, hit_f, N)
        (OUT / f"banner-{theme}.svg").write_text(svg)
        print(f"banner-{theme}.svg  {len(svg.encode()) / 1024:.0f} KB  (still frame at {hit_f / fps:.2f}s of the cast)")
        for kind, label in [("website", "Website"), ("scholar", "Google Scholar"), ("orcid", "ORCID"),
                            ("linkedin", "LinkedIn"), ("email", "Email"), ("cv", "Curriculum Vitae")]:
            (OUT / f"btn-{kind}-{theme}.svg").write_text(button(kind, label, theme, faces[2]))
    print("buttons written to", OUT)


if __name__ == "__main__":
    main()
