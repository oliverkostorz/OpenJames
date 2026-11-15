"""Write cursor moves as an SVG (no plotting dependency) to eyeball how human they look."""

from __future__ import annotations

from pathlib import Path

COLOURS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#e377c2"]


def moves_svg(moves, path: Path, size: tuple[int, int] = (1280, 900)) -> Path:
    w, h = size
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="{w}" height="{h}" fill="white" stroke="#ccc"/>']
    for i, (start, pts) in enumerate(moves):
        c = COLOURS[i % len(COLOURS)]
        seq = [start] + list(pts)
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in seq)
        out.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="1.2" opacity="0.8"/>')
        out += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.3" fill="{c}"/>' for x, y in pts]
        out.append(f'<line x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{seq[-1][0]:.1f}" y2="{seq[-1][1]:.1f}" '
                   f'stroke="#999" stroke-dasharray="4 4" stroke-width="0.8"/>')
        out.append(f'<text x="{seq[-1][0] + 4:.0f}" y="{seq[-1][1] - 4:.0f}" font-size="11" fill="{c}">{i + 1}</text>')
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))
    return path
