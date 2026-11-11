"""Helper functions for the intro notebook (IIIF section).

The notebook cells only call these functions, so that the cells shown during the presentation stay short.
Everything here is read-only: it fetches data from public IIIF servers and displays it.
"""
import html
import json
import math
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import ipywidgets as widgets
import requests
from IPython.display import HTML, display
from PIL import Image, ImageDraw

warnings.filterwarnings("ignore", message="Consider using IPython.display.IFrame")
session = requests.Session()
session.headers["User-Agent"] = "dh-workshop-iiif-notebook"


# ---------------------------------------------------------------- fetching

def get_json(url):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch(url):
    # Download a URL and return the raw bytes.
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def pil(url):
    # Download an image URL and return a PIL image together with its transfer size in bytes.
    data = fetch(url)
    return Image.open(BytesIO(data)), len(data)


def kb(n):
    return f"{n / 1024:,.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


# ---------------------------------------------------------------- URL fields (copy buttons)

def url_field(label, url, note="", open_link=True):
    # A read-only URL field with a Copy button (and optional Open link) for copying into a browser.
    # The button uses the browser clipboard; if that is blocked, the field text is selected so Ctrl+C works.
    fid = "u" + uuid.uuid4().hex[:8]
    u = html.escape(url, quote=True)
    js = (f"var i=document.getElementById('{fid}');i.select();"
          "if(navigator.clipboard){navigator.clipboard.writeText(i.value).catch(function(){document.execCommand('copy')})}"
          "else{document.execCommand('copy')};this.textContent='Copied';var b=this;setTimeout(function(){b.textContent='Copy'},1500)")
    opener = f"<a href='{u}' target='_blank' style='margin-left:8px'>open</a>" if open_link else ""
    note_html = f"<div style='color:#000000;font-size:12px;margin:2px 0 0 0'>{html.escape(note)}</div>" if note else ""
    box = (f"<div style='margin:8px 0;font:14px sans-serif'><b>{html.escape(label)}</b><br>"
           f"<input id='{fid}' readonly value='{u}' onclick='this.select()' "
           f"style='width:75%;font:13px monospace;padding:4px'>"
           f"<button onclick=\"{html.escape(js, quote=True)}\" style='margin-left:6px;padding:4px 10px'>Copy</button>"
           f"{opener}{note_html}</div>")
    return widgets.HTML(box)


def url_panel(title, fields):
    display(widgets.VBox([widgets.HTML(f"<h4 style='margin:0'>{html.escape(title)}</h4>")]
                         + [url_field(*f) if isinstance(f, tuple) else f for f in fields]))


# ---------------------------------------------------------------- manifests

def first(label_map):
    # IIIF 3 labels are language maps: {"en": ["Title"]}. Return the first value.
    return next(iter(label_map.values()))[0]


def canvas_image(canvas):
    # Follow canvas -> AnnotationPage -> Annotation -> body, and return the body and its image service URL.
    anno = canvas["items"][0]["items"][0]
    assert anno["motivation"] == "painting"
    body = anno["body"]
    service = body["service"][0] if isinstance(body["service"], list) else body["service"]
    return body, service["id"]


def thumb_strip(canvases, height=220):
    # One small image request per canvas, shown side by side.
    tiles = ""
    for cv in canvases:
        _, svc = canvas_image(cv)
        tiles += (f"<figure style='margin:0;text-align:center;font:12px sans-serif'>"
                  f"<img src='{svc}/full/,{height}/0/default.jpg' style='height:{height}px;border:1px solid #C0C0C0'>"
                  f"<figcaption>{html.escape(first(cv['label']))}</figcaption></figure>")
    display(HTML(f"<div style='display:flex;gap:12px;flex-wrap:wrap'>{tiles}</div>"))


# ---------------------------------------------------------------- Image API

def iiif_url(service, region="full", size="max", rotation="0", quality="default", fmt="jpg"):
    return f"{service}/{region}/{size}/{rotation}/{quality}.{fmt}"


def show_iiif(service, region="full", size="400,", rotation="0", quality="default"):
    # Build an Image API URL from its parts, print it and show the image it returns.
    url = iiif_url(service, region, size, rotation, quality)
    print(url)
    im, n = pil(url)
    display(HTML(f"<img src='{url}' style='max-height:420px;border:1px solid #C0C0C0'>"
                 f"<div style='font:12px sans-serif;color:#000000'>{im.width} × {im.height} px, {kb(n)}</div>"))


def show_views(service, views, width=260):
    # views: list of (title, region, size, rotation, quality). Shows each result with its URL.
    cells = ""
    for title, region, size, rot, q in views:
        url = iiif_url(service, region, size, rot, q)
        cells += (f"<figure style='margin:0;font:12px sans-serif;text-align:center;max-width:{width + 10}px'>"
                  f"<img src='{url}' style='max-width:{width}px;max-height:300px;border:1px solid #C0C0C0'>"
                  f"<figcaption><b>{html.escape(title)}</b><br>"
                  f"<code style='font-size:10px;word-break:break-all'>/{region}/{size}/{rot}/{q}.jpg</code>"
                  f"<br><a href='{url}' target='_blank'>open in browser</a></figcaption></figure>")
    display(HTML(f"<div style='display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start'>{cells}</div>"))


def render_viewport(service, info, center, scale, view=512):
    # Fetch just the tiles that cover a view x view pixel window at the given scale factor.
    # center is in full-resolution pixel coordinates. Returns the picture, the number of tiles and the bytes fetched.
    W, H = info["width"], info["height"]
    tile = info["tiles"][0]["width"]
    span = tile * scale                              # original pixels covered by one tile
    rw, rh = view * scale, view * scale              # original pixels covered by the window
    x0 = int(min(max(center[0] - rw / 2, 0), max(W - rw, 0)))
    y0 = int(min(max(center[1] - rh / 2, 0), max(H - rh, 0)))
    x1, y1 = min(x0 + rw, W), min(y0 + rh, H)

    cols = range(x0 // span, (x1 - 1) // span + 1)
    rows = range(y0 // span, (y1 - 1) // span + 1)
    jobs = []
    for r in rows:
        for c in cols:
            sx, sy = c * span, r * span
            sw, sh = min(span, W - sx), min(span, H - sy)
            out_w = math.ceil(sw / scale)
            jobs.append((c, r, f"{service}/{sx},{sy},{sw},{sh}/{out_w},/0/default.jpg"))

    with ThreadPoolExecutor(8) as ex:
        fetched = list(ex.map(lambda j: pil(j[2]), jobs))

    mosaic = Image.new("RGB", (len(cols) * tile, len(rows) * tile), "white")
    total = 0
    for (c, r, _), (im, n) in zip(jobs, fetched):
        mosaic.paste(im.convert("RGB"), ((c - cols[0]) * tile, (r - rows[0]) * tile))
        total += n
    left = (x0 - cols[0] * span) // scale
    top = (y0 - rows[0] * span) // scale
    out = mosaic.crop((left, top, left + math.ceil((x1 - x0) / scale), top + math.ceil((y1 - y0) / scale)))
    return out, len(jobs), total


def deep_zoom_demo(service, info, focus, scales=(8, 4, 2, 1)):
    # The same 512 x 512 window at increasing zoom, each built from a few tiles, with the data transferred.
    shots = []
    for s in scales:
        img, n_tiles, n_bytes = render_viewport(service, info, focus, s)
        shots.append((s, img, n_tiles, n_bytes))
    strip = Image.new("RGB", (sum(s[1].width for s in shots) + 12 * (len(shots) - 1),
                              max(s[1].height for s in shots)), "white")
    x = 0
    for _, img, _, _ in shots:
        strip.paste(img, (x, 0))
        x += img.width + 12
    display(strip)
    full_n = len(fetch(f"{service}/full/max/0/default.jpg"))
    display(HTML("<table><tr><th>scale factor</th><th>tiles requested</th><th>transferred</th></tr>" + "".join(
        f"<tr><td>{s}</td><td>{t}</td><td>{kb(b)}</td></tr>" for s, _, t, b in shots)
        + f"</table><p>For comparison, the complete image at full size is {kb(full_n)}.</p>"))


# ---------------------------------------------------------------- annotations

def make_annotation(canvas_id, region, text, n, motivation="commenting"):
    x, y, w, h = region
    return {
        "id": f"https://example.org/annotations/{n}",
        "type": "Annotation",
        "motivation": motivation,
        "body": {"type": "TextualBody", "language": "en", "format": "text/plain", "value": text},
        "target": f"{canvas_id}#xywh={x},{y},{w},{h}",
    }


def overlay(canvas, service, annotation_page, thumb_h=640):
    # Draw the annotation regions over a small version of the page (on a local copy; the server image is untouched).
    thumb, _ = pil(f"{service}/full/,{thumb_h}/0/default.jpg")
    k = thumb_h / canvas["height"]                       # canvas units -> thumbnail pixels
    draw = ImageDraw.Draw(thumb)
    for anno in annotation_page["items"]:
        x, y, w, h = map(int, anno["target"].split("#xywh=")[1].split(","))
        draw.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], outline=(220, 20, 60), width=3)
    display(thumb)


def canvas_to_image_region(region, canvas, body):
    kx, ky = body["width"] / canvas["width"], body["height"] / canvas["height"]
    x, y, w, h = region
    return tuple(round(v) for v in (x * kx, y * ky, w * kx, h * ky))


def show_annotated_regions(annotation_page, canvas, body, service):
    # Read each annotation back: take the region from its target and request exactly those pixels.
    tiles = ""
    for anno in annotation_page["items"]:
        region = tuple(int(v) for v in anno["target"].split("#xywh=")[1].split(","))
        ix, iy, iw, ih = canvas_to_image_region(region, canvas, body)
        url = f"{service}/{ix},{iy},{iw},{ih}/!300,300/0/default.jpg"
        tiles += (f"<figure style='margin:0;font:12px sans-serif;text-align:center'><img src='{url}' style='border:1px solid #C0C0C0'>"
                  f"<figcaption>{html.escape(anno['body']['value'])}<br><code>{ix},{iy},{iw},{ih}</code></figcaption></figure>")
    display(HTML(f"<div style='display:flex;gap:16px'>{tiles}</div>"))


# ---------------------------------------------------------------- Mirador

def mirador(manifest_url, canvas_id=None, height=620, view=None):
    # Build the HTML page for a Mirador 3 window that opens the given manifest.
    window = {"manifestId": manifest_url}
    if canvas_id:
        window["canvasId"] = canvas_id
    if view:
        window["view"] = view
    cfg = {"id": "viewer", "windows": [window], "window": {"allowClose": False, "allowMaximize": False},
           "workspaceControlPanel": {"enabled": False}}
    cfg_json = json.dumps(cfg).replace("</", "<\\/")
    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<link rel='stylesheet' href='https://fonts.googleapis.com/css?family=Roboto:300,400,500'>"
           "<style>html,body,#viewer{margin:0;height:100%;position:relative}</style></head><body>"
           "<div id='viewer'></div>"
           "<script src='https://cdn.jsdelivr.net/npm/mirador@3.4.3/dist/mirador.min.js'></script>"
           f"<script>Mirador.viewer({cfg_json});</script></body></html>")
    return doc


def show_mirador(*args, height=620, **kw):
    doc = mirador(*args, height=height, **kw)
    display(HTML(f"<iframe srcdoc=\"{html.escape(doc, quote=True)}\" "
                 f"style='width:100%;height:{height}px;border:1px solid #C0C0C0'></iframe>"))


def mirador_many(manifest_urls, height=620):
    # Build the HTML page for a Mirador 3 workspace with one window per manifest, in a grid.
    windows = [{"manifestId": u} for u in manifest_urls]
    cfg = {"id": "viewer", "windows": windows, "window": {"allowClose": False, "allowMaximize": False},
           "workspace": {"type": "mosaic"}, "workspaceControlPanel": {"enabled": False}}
    cfg_json = json.dumps(cfg).replace("</", "<\\/")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<link rel='stylesheet' href='https://fonts.googleapis.com/css?family=Roboto:300,400,500'>"
            "<style>html,body,#viewer{margin:0;height:100%;position:relative}</style></head><body>"
            "<div id='viewer'></div>"
            "<script src='https://cdn.jsdelivr.net/npm/mirador@3.4.3/dist/mirador.min.js'></script>"
            f"<script>Mirador.viewer({cfg_json});</script></body></html>")


def show_mirador_many(manifest_urls, height=620):
    # Show several manifests side by side in one Mirador viewer inside the notebook.
    doc = mirador_many(manifest_urls, height)
    display(HTML(f"<iframe srcdoc=\"{html.escape(doc, quote=True)}\" "
                 f"style='width:100%;height:{height}px;border:1px solid #C0C0C0'></iframe>"))


# ---------------------------------------------------------------- reading a manifest

def show_outline(manifest, depth=8, skip=("@context", "label", "metadata", "logo", "seeAlso", "within", "description", "attribution",
                                          "license", "rights", "provider", "homepage", "thumbnail", "requiredStatement", "summary")):
    # Print how a manifest is nested: its keys, the length of each list, and the first element of each list.
    # It is the same tree you see when you open the raw JSON in a browser and unfold it.
    lines = []

    def walk(x, name, indent, d):
        pad = "  " * indent
        if isinstance(x, dict):
            kind = x.get("@type") or x.get("type")
            lines.append(f"{pad}{name}" + (f"   ({kind})" if isinstance(kind, str) else ""))
            if d:
                for k, v in x.items():
                    if k not in skip and isinstance(v, (dict, list)):
                        walk(v, k, indent + 1, d - 1)
        elif isinstance(x, list):
            lines.append(f"{pad}{name}   [{len(x)} items]")
            if x and d and isinstance(x[0], (dict, list)):
                walk(x[0], "[0]", indent + 1, d - 1)

    walk(manifest, "manifest", 0, depth)
    print("\n".join(lines))


# ---------------------------------------------------------------- finding a manifest

def _is_manifest(url):
    # True if the URL answers with a IIIF Presentation manifest (v2 or v3).
    try:
        r = session.get(url, timeout=30, headers={"Accept": "application/json"})
        j = r.json() if r.ok else {}
    except Exception:
        return False
    ctx = j.get("@context", "")
    ctx = " ".join(ctx) if isinstance(ctx, list) else str(ctx)
    return "iiif.io/api/presentation" in ctx and (j.get("type") or j.get("@type", "")) in ("Manifest", "sc:Manifest")


def find_manifest(url, verbose=True):
    """Find the IIIF manifest of an object page, in two steps.
    1. Some platforms build the manifest address from the page address or the record ID: Europeana, e-codices, Fragmentarium.
    2. Otherwise the page is searched for addresses that contain 'manifest'.
    Every candidate is requested and must really answer with a manifest. Returns the URL, or None."""
    import re
    rules = [
        (r"europeana\.eu/(?:[a-z]{2}/)?item/(\d+)/([^/?#]+)", lambda m: f"https://iiif.europeana.eu/presentation/{m[1]}/{m[2]}/manifest", "Europeana: built from the record ID"),
        (r"e-codices\.(?:unifr\.)?ch/(?:[a-z]{2}/)?(?:list/one/)?([a-z]+)/(\d{4})", lambda m: f"https://www.e-codices.unifr.ch/metadata/iiif/{m[1]}-{m[2]}/manifest.json", "e-codices: built from the shelfmark"),
        (r"fragmentarium\.ms/(?:overview|view/object|view/page)/(F-[a-z0-9]+)", lambda m: f"https://fragmentarium.ms/metadata/iiif/{m[1]}/manifest.json", "Fragmentarium: built from the record ID"),
    ]
    for pattern, build, how in rules:
        m = re.search(pattern, url)
        if m and _is_manifest(build(m)):
            if verbose:
                print(f"found ({how}):\n{build(m)}")
            return build(m)
    try:
        page = session.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 dh-workshop"})
        text = page.text + " ".join(page.headers.get("Link", "").split())
    except Exception as e:
        text = ""
        if verbose:
            print(f"could not read the page ({type(e).__name__})")
    seen = []
    for cand in re.findall(r"https?://[^\s\"'<>\\]*manifest[^\s\"'<>\\]*", text.replace("\\/", "/")):
        cand = html.unescape(cand).rstrip(").,;")
        if cand not in seen:
            seen.append(cand)
            if _is_manifest(cand):
                if verbose:
                    print(f"found (the page mentions it):\n{cand}")
                return cand
    if verbose:
        print("no manifest found by pattern or in the page text. Look on the page for a IIIF logo or a link called 'IIIF' / 'Manifest' "
              "(often in a share, download or export menu), or open the developer tools, Network tab, reload, and filter by 'manifest'.")
    return None


def chain_urls(manifest_url, canvas=0):
    """The URLs that lead from a manifest to the pixels of one image, for any Presentation 2 or 3 manifest:
    manifest (Presentation API) -> canvas -> image file -> image service (Image API) -> info.json -> a region request.
    Returns a list of (label, url, note, can_open); the service entries are None if the image is a plain file."""
    m = get_json(manifest_url)
    if "sequences" in m:                                                    # Presentation 2
        cv = m["sequences"][0]["canvases"][canvas]
        res = cv["images"][0]["resource"]
        cv_id, file_url, svc = cv["@id"], res["@id"], res.get("service")
    else:                                                                   # Presentation 3
        cv = m["items"][canvas]
        body = cv["items"][0]["items"][0]["body"]
        body = body[0] if isinstance(body, list) else body
        cv_id, file_url, svc = cv["id"], body["id"], body.get("service")
    svc = svc[0] if isinstance(svc, list) else svc
    base = (svc.get("@id") or svc.get("id")).rstrip("/") if svc else None
    rows = [("1  Presentation API: the manifest", manifest_url, "One object, one URL. It lists the canvases.", True),
            (f"2  canvas {canvas + 1}: a virtual page", cv_id, "An identifier inside the manifest. Not always a working address.", False),
            ("3  the image file named in the manifest", file_url, "What the painting annotation points to.", True)]
    if base:
        info = get_json(base + "/info.json")
        w, h = info["width"], info["height"]
        rows += [("4  Image API: the image service (base URL)", base, "Found INSIDE the manifest (canvas, annotation, body, service, id). It cannot be constructed.", True),
                 ("5  Image API: info.json", base + "/info.json", f"Size of the original: {w} x {h} px. What the server can do.", True),
                 ("6  Image API: a request, here the central quarter", f"{base}/{w // 4},{h // 4},{w // 2},{h // 2}/!400,400/0/default.jpg", "{service}/{region}/{size}/{rotation}/{quality}.{format}", True)]
    else:
        rows.append(("4  no image service", "", "This image is a plain file: it can only be requested as a whole.", False))
    return rows


def show_chain(manifest_url, canvas=0):
    # Follow one image from its manifest to a region request, and show every URL on the way (see chain_urls).
    rows = chain_urls(manifest_url, canvas)
    fields = [(l, u, n, o) for l, u, n, o in rows if u]
    if not rows[-1][1]:                                                     # no image service: say where the chain ends
        fields.append(widgets.HTML("<div style='margin:8px 0;font:14px sans-serif;color:#DC143C'><b>4  no image service</b><br>"
                                   "<span style='color:#000000;font-size:12px'>The manifest names a plain image file. The Presentation API works, "
                                   "but there is no Image API behind it: no regions, no tiles, no info.json.</span></div>"))
    url_panel("From the manifest to the pixels", fields)
