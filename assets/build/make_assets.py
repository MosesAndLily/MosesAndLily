"""Generate the profile banner (light + dark) and the link buttons.

Text is shaped with HarfBuzz and converted to SVG outlines, so no fonts are needed at view time
and the banner renders identically on every device.
"""
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
    "light": dict(ink="#1b2130", ink2="#3a4152", muted="#5f6776", accent="#1e4fa3", btn_bg="#1e4fa3", btn_fg="#ffffff"),
    "dark": dict(ink="#e8e6df", ink2="#c9c7c0", muted="#9aa2b1", accent="#8db1ff", btn_bg="#8db1ff", btn_fg="#0e1117"),
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


# ----------------------------------------------------------------------------- banner
W, H = 1200, 320


def banner(theme, faces):
    c = THEMES[theme]
    news, sans, sansb, kr = faces
    x0 = 64
    eyebrow, _ = sansb.path("ROBOTICS · CONTROL · PHYSICAL INTERACTION", x0, 98, 14.5, tracking=2.6)
    name, name_w = news.path("Moses C. Nah", x0, 176, 78)
    krname, _ = kr.path("나종욱 · 羅鍾煜", x0 + name_w + 26, 174, 27)
    desc, _ = sans.path("Holiday Robotics Research Inc.  ·  Ph.D. at MIT", x0, 222, 21)
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        'aria-label="Moses C. Nah. Robotics, control, physical interaction. Holiday Robotics Research Inc.; Ph.D. at MIT.">',
        f'<path fill="{c["accent"]}" d="{eyebrow}"/>',
        f'<path fill="{c["ink"]}" d="{name}"/>',
        f'<path fill="{c["muted"]}" d="{krname}"/>',
        f'<path fill="{c["ink2"]}" d="{desc}"/>',
        f'<line x1="{x0}" y1="256" x2="{x0 + 120}" y2="256" stroke="{c["accent"]}" stroke-width="2"/>',
        "</svg>",
    ])


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
    for theme in THEMES:
        svg = banner(theme, faces)
        (OUT / f"banner-{theme}.svg").write_text(svg)
        print(f"banner-{theme}.svg  {len(svg.encode()) / 1024:.0f} KB")
        for kind, label in [("website", "Website"), ("scholar", "Google Scholar"), ("orcid", "ORCID"),
                            ("linkedin", "LinkedIn"), ("email", "Email"), ("cv", "Curriculum Vitae")]:
            (OUT / f"btn-{kind}-{theme}.svg").write_text(button(kind, label, theme, faces[2]))
    print("buttons written to", OUT)


if __name__ == "__main__":
    main()
