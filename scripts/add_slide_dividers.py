"""Insert a visual divider cell before every slide of a notebook (idempotent).

Usage: python scripts/add_slide_dividers.py notebooks/01_intro_iiif_europeana.ipynb [default-label]

A slide that happens in the browser (not in the notebook) is marked by setting "browser": true in the cell
metadata; its divider then shows a BROWSER pill (blueviolet, from misc/reference/paper_style.mplstyle).

A "slide" is a cell with "slide": true in its metadata. Banner cells (PART A / PART B / APPENDIX)
start a new part and are not given a divider themselves. Divider cells have ids starting with "div-".
Re-running removes the old dividers first.
"""
import json
import re
import sys

# Colours from misc/reference/paper_style.mplstyle (matplotlib names: rosybrown, coral, silver)
COLORS = {"PART A": "#BC8F8F", "PART B": "#FF7F50", "APPENDIX": "#C0C0C0",
          "WELCOME": "#C0C0C0", "IIIF": "#BC8F8F", "EUROPEANA": "#FF7F50"}   # section banners of the intro notebook


PILL = "#8A2BE2"   # matplotlib "blueviolet", the fifth colour of paper_style.mplstyle


def divider(label, n, total, color, browser=False):
    pill = (f'<span style="border:2.2px solid {PILL};border-radius:8px;background:#fff;color:{PILL};'
            f'padding:2px 10px;font:700 12px sans-serif;letter-spacing:.1em">BROWSER</span>') if browser else ""
    # The line is an <hr>: JupyterLab ignores a height set on a <div> here (the bar came out thick), an <hr> is always thin.
    return (f'<div style="margin:80px 0 0 0;font:600 12px sans-serif;letter-spacing:.1em;color:{color}">'
            f'<span>{label} · {n} / {total}</span>&nbsp;&nbsp;{pill}</div>'
            f'<hr style="border:0;border-top:3px solid {color};margin:6px 0 0 0">')


def main(path, default_label="SLIDES"):
    raw = open(path, encoding="utf-8").read()
    nb = json.loads(raw)
    cells = [c for c in nb["cells"] if not c["id"].startswith("div-")]

    def slide_type(c):
        return c.get("metadata", {}).get("slide")

    def banner_tag(c):
        if c["cell_type"] != "markdown":
            return None
        s = "".join(c["source"])
        if not s.startswith('<div style="border-left:8px'):
            return None
        m = re.search(r'letter-spacing:\.08em">([^<]+)<', s)
        return m.group(1) if m else None

    # first pass: group slides by part
    part, parts = default_label, []
    for c in cells:
        tag = banner_tag(c)
        if tag:
            part = tag
            parts.append((c, None))
            continue
        parts.append((c, part) if slide_type(c) else (c, None))
    totals = {}
    for c, p in parts:
        if p:
            totals[p] = totals.get(p, 0) + 1

    out, counter = [], {}
    for c, p in parts:
        if p:
            counter[p] = counter.get(p, 0) + 1
            color = COLORS.get(p, "#BC8F8F")
            out.append({"cell_type": "markdown", "id": f"div-{len(out)}",
                        "metadata": {},
                        "source": divider(p, counter[p], totals[p], color, c.get("metadata", {}).get("browser", False)).splitlines(keepends=True)})
        out.append(c)
    nb["cells"] = out
    open(path, "w", encoding="utf-8").write(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(path, totals)


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3] or []))
