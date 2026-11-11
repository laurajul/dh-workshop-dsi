"""Helper functions for notebook 04 (regions and details).

Notebook 03 embedded whole images. Here a picture is cut into regions with IIIF region URLs, each region
is embedded on its own, and the result is searched in the shared collection. The cells of the notebook only call
the functions below, so they stay short:

    Picture      an image (a corpus row, a IIIF image service, a file) that can be cropped by region
    Experiment   whole image vs. regions vs. text: the same search with different queries, side by side
    TileScan     a picture cut into overlapping tiles, each embedded; search the tiles with text
    build_manifest  IIIF manifest with your regions as annotations (#xywh=) and the images you found
    Deck         a small HTML presentation, saved with its manifest to the shared folder

Regions are always (x, y, w, h) in pixels of the full image, as in a IIIF region URL and in `canvas#xywh=x,y,w,h`.
"""
import base64
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from IPython.display import HTML, display
from PIL import Image, ImageDraw

from clip_helpers import CACHE_DIR, PROJECT_ROOT, europeana_url

Image.MAX_IMAGE_PIXELS = None
session = requests.Session()
session.headers["User-Agent"] = "dh-workshop-region-notebook"
ACCENT, CORAL, INK = "#BC8F8F", "#FF7F50", "#1f2430"
MIRADOR_JS = "https://cdn.jsdelivr.net/npm/mirador@3.4.3/dist/mirador.min.js"


# ---------------------------------------------------------------- small utilities

def jpeg_b64(im, max_side=900, quality=82):
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def img_tag(im, max_side=900, style=""):
    return f"<img src='data:image/jpeg;base64,{jpeg_b64(im, max_side)}' style='{style}'>"


def pad_square(im, fill=(124, 116, 104)):
    # CLIP resizes the short side to 224 px and cuts the centre square: a wide region would lose its sides.
    # Padding to a square keeps the whole region (and adds a grey border instead).
    s = max(im.size)
    out = Image.new("RGB", (s, s), fill)
    out.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
    return out


def embed_many(clip_model, images, fit="pad", batch=32):
    # Vectors (n, 512), L2-normalised, for a list of PIL images. fit: "pad" keeps the whole region, "crop" is CLIP's default.
    torch = clip_model._torch
    prep = [clip_model.preprocess(pad_square(im) if fit == "pad" else im.convert("RGB")) for im in images]
    out = []
    with torch.no_grad():
        for s in range(0, len(prep), batch):
            f = clip_model.model.encode_image(torch.stack(prep[s:s + batch]).to(clip_model.device)).float()
            out.append((f / f.norm(dim=-1, keepdim=True)).cpu().numpy())
    return np.concatenate(out)


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = iw * ih
    return inter / (aw * ah + bw * bh - inter)


def show_html(doc, height=620):
    # Show a complete HTML page inside the notebook (the same way the Mirador viewers of the intro notebook are shown).
    display(HTML(f"<iframe srcdoc=\"{html.escape(doc, quote=True)}\" style='width:100%;height:{height}px;border:1px solid #ccc'></iframe>"))


# ---------------------------------------------------------------- a picture and its regions

class Picture:
    """An image that can be cropped by region.

    source: a row number of the collection (int), the URL of a IIIF image service (with or without /info.json),
            the URL of a plain image, or the path of an image file.
    With an image service, a region is one URL request and only those pixels travel. Without one, the original
    file is downloaded once and cut locally.
    """

    def __init__(self, source, coll=None, label=None, credit=""):
        self.index = self.service = self.original = self.fallback = self.page = self.image_url = None
        self.credit = credit
        self._local = None
        if isinstance(source, (int, np.integer)):
            r = coll.meta[int(source)]
            self.index, self.page, self.credit = int(source), r["landing_page"], r["institution"]
            self.label = label or r["title"][:90]
            if r["iiif_service"]:
                self._init_service(r["iiif_service"])
            else:
                self.original, self.fallback = r["full_image_url"] or r["small_image_url"], r["small_image_url"]
        elif str(source).startswith("http"):
            url = str(source)
            self.label = label or url.rsplit("/", 1)[-1][:60]
            base = url[:-len("/info.json")] if url.endswith("/info.json") else url
            try:
                self._init_service(base.rstrip("/"))
            except Exception:
                self.original = url                                  # not an image service: a plain image URL
        else:
            self.label = label or Path(source).name
            self._local = Image.open(source).convert("RGB")
        if self.service is None:
            self._load_original()
        print(f"{self.label}\n{self.width} x {self.height} px, "
              + (f"IIIF image service: {self.service}" if self.service else "no image service: regions are cut locally")
              + (f"\nimage URL: {self.image_url}" if self.image_url else ""))

    def _init_service(self, base):
        info = session.get(base + "/info.json", timeout=30)
        info.raise_for_status()
        info = info.json()
        self.service, self.width, self.height = base, int(info["width"]), int(info["height"])
        self.api = 3 if "/3/" in str(info.get("@context", "")) or info.get("type") == "ImageService3" else 2

    def _load_original(self):
        if self._local is None:
            def cached(url):
                return CACHE_DIR / ("orig_" + hashlib.md5(url.encode()).hexdigest() + ".jpg")

            def fetch(url, timeout):
                path = cached(url)
                if not path.exists():
                    r = session.get(url, timeout=timeout)
                    r.raise_for_status()
                    Image.open(BytesIO(r.content)).convert("RGB").save(path, quality=95)
                return path

            try:
                path, self.image_url = fetch(self.original, 120), self.original
            except Exception as e:                                    # many original links are dead or are not images
                if not self.fallback:
                    raise
                print(f"original file not available ({type(e).__name__}); using the small version (about 400 px) instead")
                path, self.image_url = fetch(self.fallback, 60), self.fallback
            self._local = Image.open(path).convert("RGB")
        self.width, self.height = self._local.size

    # ---- regions

    def clamp(self, region):
        x, y, w, h = (int(round(v)) for v in region)
        x, y = max(0, min(x, self.width - 1)), max(0, min(y, self.height - 1))
        return x, y, max(1, min(w, self.width - x)), max(1, min(h, self.height - y))

    def frac(self, x, y, w, h):
        # A region given as fractions of the image (0 to 1) -> pixels.
        return self.clamp((x * self.width, y * self.height, w * self.width, h * self.height))

    def region_url(self, region=None, size=448, quality="default"):
        # The IIIF Image API URL of a region: {service}/{x,y,w,h}/!{size},{size}/0/{quality}.jpg
        # quality: "default" (as delivered), "color", "gray" or "bitonal" (black and white only).
        if not self.service:
            return None
        reg = "full" if region is None else ",".join(str(v) for v in self.clamp(region))
        return f"{self.service}/{reg}/!{size},{size}/0/{quality}.jpg"

    @staticmethod
    def with_quality(im, quality):
        # The same conversion done locally: for pictures without an image service, or when a server refuses the quality.
        if quality == "gray":
            return im.convert("L").convert("RGB")
        if quality == "bitonal":
            return im.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("RGB")
        return im

    def crop(self, region=None, size=448, quality="default"):
        # The pixels of a region as a PIL image, at most `size` pixels on the long side.
        # quality: "default", "gray" or "bitonal" (asked from the image server when there is one, otherwise converted here).
        if self.service:
            # Some image servers only deliver certain sizes (level 1) and answer others with an error: try smaller ones.
            for s in dict.fromkeys([size] + [v for v in (800, 600, 448, 256) if v < size]):
                r = session.get(self.region_url(region, s, quality), timeout=60)
                if r.ok:
                    return Image.open(BytesIO(r.content)).convert("RGB")
            if quality != "default":                                   # the server does not offer this quality: convert here
                return self.with_quality(self.crop(region, size), quality)
            r.raise_for_status()
        im = self._local if region is None else self._local.crop((lambda x, y, w, h: (x, y, x + w, y + h))(*self.clamp(region)))
        im = im.copy()
        im.thumbnail((size, size))
        return self.with_quality(im, quality)

    def show(self, regions=None, size=900, keep=True):
        # The picture with its regions outlined and numbered, and the request behind each region.
        regions = regions or {}
        ov = self.crop(None, size)
        k = ov.width / self.width
        d = ImageDraw.Draw(ov)
        for n, (name, reg) in enumerate(regions.items(), 1):
            x, y, w, h = self.clamp(reg)
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], outline=(220, 20, 60), width=3)
            d.text((x * k + 5, y * k + 3), f"{n} {name}", fill=(220, 20, 60))
        display(ov)
        if keep:
            from keep_helpers import keep_button
            keep_button(lambda: ov, f"{self.label}, regions")
        rows = "".join(f"<tr><td style='padding-right:12px'>{n} {html.escape(str(name))}</td><td><code>{html.escape(self.region_url(r) or 'cut locally from the original: ' + str(self.clamp(r)))}</code></td></tr>"
                       for n, (name, r) in enumerate(regions.items(), 1))
        if rows:
            display(HTML(f"<table style='font:12px sans-serif'>{rows}</table>"))


# ---------------------------------------------------------------- search: whole image vs. regions vs. text

def cards_html(coll, idx, scores=None, size=110):
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(coll.small_image, idx))
    out = ""
    for i in idx:
        r = coll.meta[int(i)]
        sc = f"<br>{scores[i]:.3f}" if scores is not None else ""
        link = f"<br><a href='{europeana_url(r['id'])}' target='_blank' title='row {int(i)} of metadata.csv'>#{int(i)} Europeana</a>"
        out += (f"<figure style='margin:0;width:{size}px;font:10px sans-serif'>{coll.thumb(int(i), size)}"
                f"<figcaption title='{html.escape(r['title'][:120], quote=True)}'>{html.escape(r['institution'][:22])}{sc}{link}</figcaption></figure>")
    return out


class Experiment:
    """The same search with different queries, side by side.

        exp = Experiment(coll, clip_model, picture)
        exp.add("whole image")                           # region=None: the full picture
        exp.add("the dog", region=(x, y, w, h))          # a region of the picture
        exp.add("grey", region, quality="gray")          # the same region as "gray" or "bitonal" (black and white only)
        exp.add("text", text="a dog")                    # a text query
        exp.run(k=12); exp.show(); exp.overlap()
    """

    def __init__(self, coll, clip_model, picture=None, mask=None):
        self.coll, self.clip, self.picture, self.mask = coll, clip_model, picture, mask
        self.queries = {}                                  # name -> dict(vec, preview, region, text)
        self.results = {}                                  # name -> dict(top, scores)

    def add(self, name, region="full", text=None, fit="pad", quality="default"):
        if text is not None:
            self.queries[name] = dict(vec=self.clip.text(text), preview=None, region=None, text=text)
        else:
            region = None if (isinstance(region, str) and region == "full") else region
            crop = self.picture.crop(region, 448, quality)
            self.queries[name] = dict(vec=embed_many(self.clip, [crop], fit)[0], preview=crop, region=region, text=None)

    def add_vector(self, name, vec, preview=None):
        # Any vector, e.g. a mix of a region and a text: exp.add_vector("dog but gold", v / np.linalg.norm(v))
        self.queries[name] = dict(vec=np.asarray(vec, dtype=np.float32), preview=preview, region=None, text=None)

    def run(self, k=12):
        self.k = k
        for name, q in self.queries.items():
            s = self.coll.similarity(q["vec"].astype(np.float32))
            if self.picture is not None and self.picture.index is not None:
                s[self.picture.index] = -np.inf             # do not return the picture itself
            self.results[name] = dict(top=self.coll.top_k(s, k, self.mask), scores=s)
        return self

    def top(self, name, n=None):
        t = self.results[name]["top"]
        return t if n is None else t[:n]

    def html(self, size=110):
        rows = ""
        for name, q in self.queries.items():
            res = self.results[name]
            if q["preview"] is not None:
                shown = img_tag(q["preview"], 160, "height:100px;width:auto;border:2px solid #dc143c")
            else:
                shown = f"<div style='width:140px;height:100px;background:#f3eeee;font:italic 13px sans-serif;padding:6px;box-sizing:border-box'>{html.escape(q['text'] or '')}</div>"
            rows += (f"<div style='display:flex;gap:12px;align-items:flex-start;margin:0 0 14px 0'>"
                     f"<div style='width:160px;font:600 12px sans-serif'>{html.escape(name)}<br>{shown}</div>"
                     f"<div style='display:flex;gap:6px;flex-wrap:wrap'>{cards_html(self.coll, res['top'], res['scores'], size)}</div></div>")
        return rows

    def show(self, size=110, keep=True):
        display(HTML(self.html(size)))
        if keep:
            from keep_helpers import contact_sheet, keep_button
            keep_button(lambda: contact_sheet([(n, [self.coll.small_image(int(i)) for i in self.results[n]["top"]]) for n in self.results]),
                        "Search with whole image and regions")

    def overlap(self):
        # How many of the top results two queries share, and how many different institutions each one reaches.
        names = list(self.queries)
        sets = {n: set(map(int, self.results[n]["top"])) for n in names}
        head = "".join(f"<th style='padding:2px 8px'>{html.escape(n[:18])}</th>" for n in names)
        body = ""
        for a in names:
            cells = "".join(f"<td style='text-align:center;background:{ACCENT}{int(15 + 200 * len(sets[a] & sets[b]) / max(len(sets[a]), 1)):02x}'>{len(sets[a] & sets[b])}</td>" for b in names)
            n_inst = len(set(self.coll.institution[list(sets[a])]))
            body += f"<tr><th style='text-align:left;padding-right:8px'>{html.escape(a[:18])}</th>{cells}<td style='padding-left:12px'>{n_inst} institutions</td></tr>"
        display(HTML(f"<b>Shared results in the top {self.k}</b><table style='font:12px sans-serif;border-collapse:collapse'><tr><th></th>{head}<th></th></tr>{body}</table>"))


# ---------------------------------------------------------------- tiles

class TileScan:
    """Cut a picture into overlapping square tiles, embed each, and search the tiles with text.

    rows: how many tiles fit across the short side of the picture (the tile is min(width, height) / rows pixels);
    overlap: 0.5 means neighbours share half a tile. quality: "default", "gray" or "bitonal".
    One request per tile when the picture has an image service, so a very large picture needs a coarse grid.
    """

    def __init__(self, picture, clip_model, rows=4, overlap=0.5, size=256, fit="pad", quality="default", max_tiles=600, workers=8):
        self.picture, self.clip, self.fit = picture, clip_model, fit
        tile = max(32, min(picture.width, picture.height) // rows)
        step = max(1, int(tile * (1 - overlap)))
        xs = list(range(0, max(1, picture.width - tile + 1), step))
        ys = list(range(0, max(1, picture.height - tile + 1), step))
        if xs[-1] + tile < picture.width:
            xs.append(picture.width - tile)
        if ys[-1] + tile < picture.height:
            ys.append(picture.height - tile)
        self.regions = [picture.clamp((x, y, tile, tile)) for y in ys for x in xs]
        if len(self.regions) > max_tiles:
            raise ValueError(f"{len(self.regions)} tiles is too many (max_tiles={max_tiles}). Use fewer rows or less overlap.")
        print(f"{len(self.regions)} tiles of {tile} x {tile} px ({len(xs)} columns x {len(ys)} rows). Fetching and embedding ...")
        with ThreadPoolExecutor(workers) as ex:
            crops = list(ex.map(lambda r: picture.crop(r, size, quality), self.regions))
        self.V = embed_many(clip_model, crops, fit)
        print("done.")

    def scores(self, query):
        q = self.clip.text(query) if isinstance(query, str) else np.asarray(query, dtype=np.float32)
        return self.V @ q

    def best(self, query, k=5, max_iou=0.2):
        # The k best tiles, skipping tiles that overlap a better one (non-maximum suppression).
        s = self.scores(query)
        keep = []
        for i in np.argsort(-s):
            if all(iou(self.regions[i], self.regions[j]) <= max_iou for j in keep):
                keep.append(int(i))
            if len(keep) == k:
                break
        return [(self.regions[i], float(s[i])) for i in keep]

    def show(self, query, k=5, size=1100, heat=True):
        # The picture with a heat map of the tile scores and the k best tiles outlined.
        s = self.scores(query)
        ov = self.picture.crop(None, size).convert("RGBA")
        f = ov.width / self.picture.width
        if heat:
            layer = Image.new("RGBA", ov.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            lo, hi = float(s.min()), float(s.max())
            for i in np.argsort(s):                                 # strongest tiles are drawn last
                x, y, w, h = self.regions[i]
                a = int(150 * (s[i] - lo) / (hi - lo + 1e-9))
                d.rectangle([x * f, y * f, (x + w) * f, (y + h) * f], fill=(255, 80, 40, a))
            ov = Image.alpha_composite(ov, layer)
        d = ImageDraw.Draw(ov)
        top = self.best(query, k)
        for n, (r, sc) in enumerate(top, 1):
            x, y, w, h = r
            d.rectangle([x * f, y * f, (x + w) * f, (y + h) * f], outline=(255, 255, 255), width=4)
            d.rectangle([x * f, y * f, (x + w) * f, (y + h) * f], outline=(220, 20, 60), width=2)
            d.text((x * f + 5, y * f + 4), str(n), fill=(255, 255, 255))
        display(ov.convert("RGB"))
        strip = "".join(f"<figure style='margin:0;font:11px sans-serif'>{img_tag(self.picture.crop(r, 256), 256, 'height:150px;width:auto')}"
                        f"<figcaption>{n}  {sc:.3f}</figcaption></figure>" for n, (r, sc) in enumerate(top, 1))
        display(HTML(f"<b>{html.escape(query if isinstance(query, str) else 'vector')}</b><div style='display:flex;gap:10px'>{strip}</div>"))
        return top


# ---------------------------------------------------------------- annotations and manifest

def note(region, text, hits=None):
    # One annotation: a region of the picture, a text, and optionally the collection rows found for that region.
    return dict(region=tuple(int(v) for v in region), text=text, hits=[int(h) for h in (hits if hits is not None else [])])


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled"


def _image_body(picture, size=1000):
    body = {"type": "Image", "format": "image/jpeg"}
    if picture.service:
        scale = min(1, size / max(picture.width, picture.height))
        body.update(id=f"{picture.service}/full/!{size},{size}/0/default.jpg",
                    width=max(1, round(picture.width * scale)), height=max(1, round(picture.height * scale)),
                    service=[{"id": picture.service, "type": f"ImageService{picture.api}", "profile": "level2"}])
    else:
        body.update(id=f"data:image/jpeg;base64,{jpeg_b64(picture._local, 1600)}", width=picture.width, height=picture.height)
    return body


def build_manifest(title, picture, notes, coll=None, summary=""):
    """A IIIF Presentation 3 manifest: canvas 1 is your picture with one annotation per region (target canvas#xywh=...),
    then one canvas per image found in the collection. A range per annotation lists the images found for it."""
    mid = f"https://example.org/workshop/{slug(title)}"
    c0 = f"{mid}/canvas/0"
    items = [{"id": c0, "type": "Canvas", "label": {"en": [picture.label]}, "width": picture.width, "height": picture.height,
              "items": [{"id": f"{c0}/page", "type": "AnnotationPage", "items": [{"id": f"{c0}/page/image", "type": "Annotation", "motivation": "painting",
                                                                                "body": _image_body(picture), "target": c0}]}],
              "annotations": []}]
    structures, canvas_of = [], {}

    def hit_canvas(i):
        if i not in canvas_of:
            r = coll.meta[i]
            w, h = coll.small_image(i).size
            cid = f"{mid}/canvas/{len(items)}"
            canvas_of[i] = cid
            items.append({"id": cid, "type": "Canvas", "label": {"en": [r["title"][:120] or "untitled"]}, "width": w, "height": h,
                          "metadata": [{"label": {"en": ["Institution"]}, "value": {"en": [r["institution"]]}},
                                       {"label": {"en": ["Rights"]}, "value": {"en": [r["rights"]]}}],
                          "homepage": [{"id": r["landing_page"], "type": "Text", "label": {"en": ["Object page"]}, "format": "text/html"}] if r["landing_page"] else [],
                          "items": [{"id": f"{cid}/page", "type": "AnnotationPage", "items": [{"id": f"{cid}/page/image", "type": "Annotation", "motivation": "painting",
                                                                                              "body": {"id": r["small_image_url"], "type": "Image", "format": "image/jpeg", "width": w, "height": h}, "target": cid}]}]})
        return canvas_of[i]

    annos = []
    for n, nt in enumerate(notes, 1):
        x, y, w, h = picture.clamp(nt["region"])
        body = f"<p>{html.escape(nt['text'])}</p>"
        if nt["hits"]:
            # Mirador's sidebar ignores image sizes, so the hits are listed as links; the images are canvases of this manifest.
            body += "<ul>" + "".join(f"<li><a href='{html.escape(coll.meta[i]['landing_page'], quote=True)}' target='_blank'>{html.escape(coll.meta[i]['title'][:60] or 'untitled')}</a>, {html.escape(coll.meta[i]['institution'][:30])}</li>" for i in nt["hits"]) + "</ul>"
        annos.append({"id": f"{c0}/annotation/{n}", "type": "Annotation", "motivation": "commenting",
                      "body": {"type": "TextualBody", "language": "en", "format": "text/html", "value": body},
                      "target": f"{c0}#xywh={x},{y},{w},{h}"})
        if nt["hits"]:
            structures.append({"id": f"{mid}/range/{n}", "type": "Range", "label": {"en": [f"Region {n}: {nt['text'][:50]}"]},
                               "items": [{"id": f"{c0}#xywh={x},{y},{w},{h}", "type": "Canvas"}] + [{"id": hit_canvas(i), "type": "Canvas"} for i in nt["hits"]]})
    items[0]["annotations"] = [{"id": f"{c0}/annotations", "type": "AnnotationPage", "items": annos}]
    manifest = {"@context": "http://iiif.io/api/presentation/3/context.json", "id": f"{mid}/manifest", "type": "Manifest",
                "label": {"en": [title]}, "items": items}
    if summary:
        manifest["summary"] = {"en": [summary]}
    if structures:
        manifest["structures"] = structures
    return manifest


def mirador_page(manifest, canvas=0):
    # A Mirador page with the manifest inside, so no server is needed: the page turns the manifest into a blob: URL and opens that.
    # (Mirador 3.4 does not read a manifest from its config; it always fetches a URL.) The annotation panel opens by default.
    cfg = {"id": "viewer", "windows": [{"canvasId": manifest["items"][canvas]["id"]}],
           "window": {"allowClose": False, "allowMaximize": False, "defaultSideBarPanel": "annotations", "sideBarOpenByDefault": True,
                      "forceDrawAnnotations": True, "highlightAllAnnotations": True},
           "workspaceControlPanel": {"enabled": False}}
    cfg_json = json.dumps(cfg).replace("</", "<\\/")
    man_json = json.dumps(manifest).replace("</", "<\\/")
    return ("<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='https://fonts.googleapis.com/css?family=Roboto:300,400,500'>"
            "<style>html,body,#viewer{margin:0;height:100%;position:relative}</style></head><body><div id='viewer'></div>"
            f"<script src='{MIRADOR_JS}'></script><script>var cfg={cfg_json},man={man_json};"
            "cfg.windows[0].manifestId=URL.createObjectURL(new Blob([JSON.stringify(man)],{type:'application/json'}));Mirador.viewer(cfg);</script></body></html>")


def show_manifest(manifest, height=620):
    show_html(mirador_page(manifest), height)


# ---------------------------------------------------------------- the presentation

class Deck:
    """A small HTML presentation (arrow keys or buttons). Everything is inside one file: images are embedded,
    Mirador is loaded from a CDN. Add slides in the order you want to present them, then .show() and .save()."""

    CSS = f"""
    body{{margin:0;font:18px/1.45 sans-serif;color:{INK};background:#fff}}
    .slide{{display:none;padding:28px 44px;height:calc(100vh - 60px);box-sizing:border-box;overflow:auto}}
    .slide.on{{display:block}} h1{{font-size:40px;margin:0 0 6px}} h2{{font-size:28px;margin:0 0 14px;border-left:8px solid {ACCENT};padding-left:12px}}
    .sub{{color:#666}} li{{margin:4px 0}} .row{{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}}
    nav{{position:fixed;bottom:0;left:0;right:0;height:44px;background:#f6f1f1;display:flex;align-items:center;gap:12px;padding:0 20px;font-size:14px}}
    nav button{{border:1px solid {ACCENT};background:#fff;border-radius:4px;padding:4px 14px;cursor:pointer}} iframe{{border:1px solid #ccc;width:100%}}
    """

    def __init__(self, title, author="", subtitle=""):
        self.title, self.slides = title, []
        self.slides.append(f"<h1>{html.escape(title)}</h1><p class='sub'>{html.escape(subtitle)}</p><p>{html.escape(author)}</p>")

    @staticmethod
    def _text(text):
        out, items = "", []
        for line in text.strip().splitlines():
            if line.startswith("- "):
                items.append(f"<li>{html.escape(line[2:])}</li>")
            else:
                if items:
                    out, items = out + "<ul>" + "".join(items) + "</ul>", []
                if line.strip():
                    out += f"<p>{html.escape(line)}</p>"
        return out + ("<ul>" + "".join(items) + "</ul>" if items else "")

    def add_text(self, heading, text):
        self.slides.append(f"<h2>{html.escape(heading)}</h2>{self._text(text)}")

    def add_picture(self, heading, picture, regions=None, text=""):
        # The picture with its regions outlined, and each region as its own crop.
        regions = regions or {}
        ov = picture.crop(None, 900)
        k = ov.width / picture.width
        d = ImageDraw.Draw(ov)
        for n, (name, reg) in enumerate(regions.items(), 1):
            x, y, w, h = picture.clamp(reg)
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], outline=(220, 20, 60), width=4)
            d.text((x * k + 6, y * k + 4), str(n), fill=(220, 20, 60))
        crops = "".join(f"<figure style='margin:0 0 10px 0;font-size:13px'>{img_tag(picture.crop(r, 300), 300, 'max-height:130px;width:auto')}<figcaption>{n} {html.escape(str(name))}</figcaption></figure>"
                        for n, (name, r) in enumerate(regions.items(), 1))
        credit = f"<p class='sub' style='font-size:13px'>{html.escape(picture.label)}, {html.escape(picture.credit)}</p>"
        self.slides.append(f"<h2>{html.escape(heading)}</h2><div class='row'><div>{img_tag(ov, 900, 'max-height:62vh;max-width:60vw')}{credit}</div>"
                           f"<div>{crops}</div></div>{self._text(text)}")

    def add_compare(self, heading, exp, text=""):
        self.slides.append(f"<h2>{html.escape(heading)}</h2>{exp.html(100)}{self._text(text)}")

    def add_results(self, heading, coll, idx, scores=None, text=""):
        self.slides.append(f"<h2>{html.escape(heading)}</h2><div style='display:flex;gap:8px;flex-wrap:wrap'>{cards_html(coll, idx, scores, 150)}</div>{self._text(text)}")

    def add_mirador(self, heading, manifest, text=""):
        doc = html.escape(mirador_page(manifest), quote=True)
        self.slides.append(f"<h2>{html.escape(heading)}</h2><iframe srcdoc=\"{doc}\" style='height:68vh'></iframe>{self._text(text)}")

    def html(self):
        body = "".join(f"<section class='slide{' on' if i == 0 else ''}'>{s}</section>" for i, s in enumerate(self.slides))
        js = ("var s=document.querySelectorAll('.slide'),i=0,c=document.getElementById('c');"
              "function go(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach(function(e,k){e.classList.toggle('on',k==i)});c.textContent=(i+1)+' / '+s.length}"
              "document.getElementById('p').onclick=function(){go(i-1)};document.getElementById('n').onclick=function(){go(i+1)};"
              "document.addEventListener('keydown',function(e){if(e.key=='ArrowRight'||e.key==' ')go(i+1);if(e.key=='ArrowLeft')go(i-1)});go(0);")
        return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(self.title)}</title>"
                f"<style>{self.CSS}</style></head><body>{body}<nav><button id='p'>&larr;</button><button id='n'>&rarr;</button><span id='c'></span></nav><script>{js}</script></body></html>")

    def show(self, height=640):
        show_html(self.html(), height)

    def save(self, path):
        Path(path).write_text(self.html(), encoding="utf-8")
        return path


SWITCH_URL = "https://drive.switch.ch/index.php/s/JeirWKGtP2HBxEm"


def submission_dir(name):
    # submissions/<name>/ in the project folder (next to the notebooks, in the file browser). The shared folder is read-only:
    # the files are handed in through the Switch drive (see hand_in_message).
    d = PROJECT_ROOT / "submissions" / slug(name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def hand_in_message(d):
    return (f"\nHand in: the files are in {d.relative_to(PROJECT_ROOT)}/ (file browser on the left; right-click a file, Download).\n"
            f"Then open {SWITCH_URL}, create a folder with your name and drop the files in.\n"
            f"You can add anything else you want to show: a screenshot, a few images, an .html page.")


def save_submission(name, deck, manifest):
    d = submission_dir(name)
    deck.save(d / "index.html")
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved to {d}\n  index.html     the presentation (open it in a browser)\n  manifest.json  the IIIF manifest with your annotations" + hand_in_message(d))
    return d


def submit_notebook(name, notebook, html_copy=True, extra_files=()):
    """Copy your own notebook into submissions/<name>/ (together with an HTML copy that shows its outputs
    and opens in any browser without running anything). Save the notebook first (Ctrl+S), so the outputs are in the file."""
    import shutil
    import subprocess
    import sys
    nb = Path(notebook)
    if not nb.exists():
        raise FileNotFoundError(f"{nb} not found: give the file name of your notebook, e.g. 'my_notebook.ipynb'")
    d = submission_dir(name)
    shutil.copy(nb, d / nb.name)
    for f in extra_files:
        shutil.copy(f, d / Path(f).name)
    if html_copy:
        r = subprocess.run([sys.executable, "-m", "nbconvert", "--to", "html", "--output-dir", str(d), str(nb)], capture_output=True, text=True)
        print("HTML copy written." if r.returncode == 0 else f"HTML copy failed (the notebook itself was copied):\n{r.stderr[-300:]}")
    print(f"saved to {d}" + hand_in_message(d))
    return d


def find_large(coll, n=12, sample=300, seed=0, mask=None):
    """Which pictures of the collection are large (and so have detail)? Asks the image services of a random sample of the
    pictures that have one (a small request each) and shows the n largest, with their size. Returns their row numbers."""
    rows = np.flatnonzero(coll.has_iiif if mask is None else (coll.has_iiif & mask))
    pick = np.random.default_rng(seed).choice(rows, min(sample, len(rows)), replace=False)

    def dims(i):
        try:
            j = session.get(coll.meta[int(i)]["iiif_service"] + "/info.json", timeout=20).json()
            return int(i), int(j["width"]), int(j["height"])
        except Exception:
            return int(i), 0, 0
    with ThreadPoolExecutor(16) as ex:
        found = sorted((d for d in ex.map(dims, pick) if d[1]), key=lambda d: -d[1] * d[2])[:n]
    idx = [d[0] for d in found]
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(coll.small_image, idx))
    cards = "".join(f"<figure style='margin:0;width:150px;font:11px sans-serif'>{coll.thumb(i, 150)}<figcaption><b>#{k}</b> {w} x {h} px<br>{html.escape(coll.meta[i]['title'][:44])}</figcaption></figure>"
                    for k, (i, w, h) in enumerate(found))
    display(HTML(f"<div style='display:flex;gap:10px;flex-wrap:wrap'>{cards}</div>"))
    return idx
