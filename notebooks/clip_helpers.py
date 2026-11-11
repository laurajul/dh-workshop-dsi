"""Helper functions for notebook 03 (CLIP search).

The notebook cells only call these functions, so that the cells shown during the presentation stay short.
The shared dataset holds no images: only metadata, links and precomputed CLIP vectors. Small images are
fetched from the institutions on demand and cached under data/image_cache/.
"""
import csv
import hashlib
import html
import os
from base64 import b64encode
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from IPython.display import HTML, display
from PIL import Image

NOTEBOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = NOTEBOOK_DIR.parent

# The shared dataset (metadata.csv + embeddings/ + models/) is looked for, in this order:
#   1. the folder in the environment variable DSI_WORKSHOP_DIR
#   2. ~/shared/DSI-Workshop
#   3. ~/data (the link that setup.sh makes to the shared folder on the workshop server)
#   4. data/DSI-Workshop inside the project
def _find_data():
    if os.environ.get("DSI_WORKSHOP_DIR"):
        return Path(os.environ["DSI_WORKSHOP_DIR"])
    for d in (Path.home() / "shared" / "DSI-Workshop", Path.home() / "data"):
        if (d / "metadata.csv").exists():
            return d
    return PROJECT_ROOT / "data" / "DSI-Workshop"


DATA = _find_data()
CACHE_DIR = PROJECT_ROOT / "data" / "image_cache"      # downloaded small images are kept here
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def manifest_url(record_id):
    # Europeana publishes a IIIF manifest for every record, at an address built from the record ID.
    dataset, local = record_id.strip("/").split("/", 1)
    return f"https://iiif.europeana.eu/presentation/{dataset}/{local}/manifest"


def europeana_url(record_id):
    # The page of a record on europeana.eu, built from its ID ("/916118/S_TEK_photo_TEKA0214991").
    return "https://www.europeana.eu/en/item/" + record_id.strip("/")


def bar_table(pairs, total, title):
    rows = "".join(f"<tr><td style='padding-right:10px'>{html.escape(k[:48])}</td><td style='text-align:right;padding-right:8px'>{v:,}</td>"
                   f"<td><div style='background:#BC8F8F;height:10px;width:{max(v / total * 220, 1):.0f}px'></div></td></tr>" for k, v in pairs)
    return f"<div><b>{title}</b><table style='font:12px sans-serif'>{rows}</table></div>"


# ---------------------------------------------------------------- the collection

class Collection:
    """Metadata and CLIP vectors of the shared dataset, in the same order (row i of meta is vector i of V)."""

    def __init__(self):
        with open(DATA / "metadata.csv", encoding="utf-8") as f:
            self.meta = list(csv.DictReader(f))
        npz = np.load(DATA / "embeddings" / "clip_vit_b32.npz")
        self.V = npz["vectors"]                                   # (N, 512), already L2-normalised
        assert list(npz["ids"]) == [r["id"] for r in self.meta], "metadata.csv and embeddings are not aligned"
        m = self.meta
        self.institution = np.array([r["institution"] for r in m])
        self.country = np.array([r["country"] for r in m])
        self.year = np.array([int(r["year"]) if r["year"].isdigit() else 0 for r in m])
        self.has_iiif = np.array([bool(r["iiif_service"]) for r in m])

    def summary(self):
        print(f"{len(self.meta):,} images from {len(set(self.institution)):,} institutions in {len(set(self.country))} countries")
        print(f"embeddings: {self.V.shape}, {self.V.dtype}, {self.V.nbytes / 1e6:,.1f} MB")
        print(f"images with a working IIIF image service: {self.has_iiif.sum():,} ({self.has_iiif.mean():.1%})")
        print(f"images with a year: {(self.year > 0).sum():,}")
        per = np.array(list(Counter(self.institution).values()))
        print(f"images per institution: at most {per.max():,} (the sample is capped; {(per == per.max()).sum():,} institutions reach it), median {int(np.median(per)):,}")

    # ---- images (fetched from the institutions, cached locally)

    def load_small(self, i):
        # The small image of row i: from the local cache if present, otherwise from its URL. Returns (PIL image, bytes).
        path = CACHE_DIR / (hashlib.md5(self.meta[i]["id"].encode()).hexdigest() + ".jpg")
        if not path.exists():
            r = requests.get(self.meta[i]["small_image_url"], timeout=45)
            r.raise_for_status()
            path.write_bytes(r.content)
        return Image.open(path).convert("RGB"), path.stat().st_size

    def small_image(self, i):
        try:
            return self.load_small(i)[0]
        except Exception:
            return Image.new("RGB", (170, 170), "#ddd")         # the source did not answer

    def thumb(self, i, size=170):
        # An <img> tag with the image embedded, so that it shows in any notebook front end.
        im = self.small_image(i)
        im.thumbnail((size * 2, size * 2))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=80)
        return (f"<img src='data:image/jpeg;base64,{b64encode(buf.getvalue()).decode()}' "
                f"style='width:{size}px;height:{size}px;object-fit:cover;background:#eee'>")

    def show_grid(self, indices, scores=None, size=170, numbered=False, keep=True, caption="Search results"):
        # Show results as cards. numbered=True adds #0, #1, ... so that a result can be picked by number.
        with ThreadPoolExecutor(8) as ex:                          # fetch the images of the results in parallel
            list(ex.map(self.small_image, indices))
        cards = ""
        for n, i in enumerate(indices):
            r = self.meta[i]
            num = f"<b style='color:#BC8F8F'>#{n}</b> " if numbered else ""
            score = f"<br><b>similarity {scores[i]:.3f}</b>" if scores is not None else ""
            yr = f", {r['year']}" if r["year"] else ""
            link = f"<br><a href='{europeana_url(r['id'])}' target='_blank'>Europeana</a> · row {int(i)}"
            cards += (f"<figure style='margin:0;width:{size}px;font:11px sans-serif'>{self.thumb(i, size)}"
                      f"<figcaption>{num}<b>{html.escape(r['title'][:60])}</b><br>{html.escape(r['institution'][:38])}{yr}{score}{link}</figcaption></figure>")
        display(HTML(f"<div style='display:flex;gap:12px;flex-wrap:wrap'>{cards}</div>"))
        if keep:                                                   # a button that saves the results for the presentation
            from keep_helpers import contact_sheet, keep_button
            keep_button(lambda: contact_sheet([(caption, [self.small_image(i) for i in indices])]), caption)

    # ---- search

    def similarity(self, q, chunk=200_000):
        # Dot product of the query with every image vector (in chunks, so large collections fit in memory).
        out = np.empty(len(self.V), dtype=np.float32)
        for s in range(0, len(self.V), chunk):
            out[s:s + chunk] = self.V[s:s + chunk].astype(np.float32) @ q
        return out

    def top_k(self, scores, k=12, mask=None):
        s = scores if mask is None else np.where(mask, scores, -np.inf)
        idx = np.argpartition(-s, min(k, len(s) - 1))[:k]
        idx = idx[np.argsort(-s[idx])]
        return idx[np.isfinite(s[idx])]

    def institution_share(self, top, query, n=8):
        # Institutions among the top results, compared with their share of the whole collection.
        in_top = Counter(self.institution[top]).most_common(n)
        share_all = Counter(self.institution)
        rows = "".join(
            f"<tr><td style='padding-right:10px'>{html.escape(name[:48])}</td><td style='text-align:right;padding-right:10px'>{c}%</td>"
            f"<td style='text-align:right;padding-right:10px'>{share_all[name] / len(self.meta):.1%}</td></tr>" for name, c in in_top)
        display(HTML(f"<b>{html.escape(query)}</b>: institutions in the top {len(top)} results<table style='font:12px sans-serif'>"
                     "<tr><th style='text-align:left'>Institution</th><th>share of top results</th><th>share of collection</th></tr>" + rows + "</table>"))

    def top_institutions_and_countries(self, n=10):
        by_inst = Counter(self.institution).most_common(n)
        by_country = Counter(self.country).most_common(n)
        display(HTML("<div style='display:flex;gap:40px;flex-wrap:wrap'>"
                     + bar_table(by_inst, by_inst[0][1], "Institutions with the most images")
                     + bar_table(by_country, by_country[0][1], "Countries with the most images") + "</div>"))

    # ---- look closely

    def look_closely(self, i, size=1000, region=None):
        # region: (x, y, w, h) as fractions of the image, e.g. (0.25, 0.25, 0.5, 0.5) for the central quarter.
        r = self.meta[i]
        small, small_bytes = self.load_small(i)

        if r["iiif_service"]:
            reg = "full" if region is None else "pct:" + ",".join(f"{v * 100:.2f}" for v in region)
            url = f"{r['iiif_service']}/{reg}/!{size},{size}/0/default.jpg"
            data = requests.get(url, timeout=60).content
            big, how = Image.open(BytesIO(data)).convert("RGB"), "IIIF image service"
        else:
            url = r["full_image_url"]
            data = requests.get(url, timeout=120).content
            big, how = Image.open(BytesIO(data)).convert("RGB"), "original file (no image service)"
            if region is not None:
                W, H = big.size
                big = big.crop((int(region[0] * W), int(region[1] * H), int((region[0] + region[2]) * W), int((region[1] + region[3]) * H)))
            big.thumbnail((size, size))

        print(f"{r['title'][:70]}\n{r['institution']}")
        print(f"request:  {how}\n          {url}")
        print(f"small version used for the embedding: {small.size[0]} x {small.size[1]}, {small_bytes / 1024:,.0f} KB")
        print(f"requested version:             {big.size[0]} x {big.size[1]}, transferred {len(data) / 1024:,.0f} KB")
        print("Europeana:  ", europeana_url(r["id"]))
        if r["landing_page"]:
            print("object page:", r["landing_page"])

        h = min(520, big.height)
        strip = Image.new("RGB", (int(small.width * h / small.height) + int(big.width * h / big.height) + 12, h), "white")
        a = small.resize((int(small.width * h / small.height), h))
        b = big.resize((int(big.width * h / big.height), h))
        strip.paste(a, (0, 0))
        strip.paste(b, (a.width + 12, 0))
        display(strip)


# ---------------------------------------------------------------- CLIP

class Clip:
    """The CLIP model (ViT-B/32). Only needed to turn a text or your own image into a vector."""

    def __init__(self):
        import clip
        import torch
        self._clip, self._torch = clip, torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model_dirs = [DATA / "models", DATA / "models" / "CLIP", PROJECT_ROOT / "models" / "CLIP"]
        model_dir = next((d for d in model_dirs if (d / "ViT-B-32.pt").exists()), model_dirs[0])
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device, download_root=str(model_dir))
        self.model.eval()
        print(f"CLIP ViT-B/32 loaded on {self.device} from {model_dir}")

    def text(self, text):
        torch = self._torch
        with torch.no_grad():
            f = self.model.encode_text(self._clip.tokenize([text], truncate=True).to(self.device)).float()
            f = f / f.norm(dim=-1, keepdim=True)
        return f[0].cpu().numpy()

    def image(self, pil_image):
        torch = self._torch
        with torch.no_grad():
            f = self.model.encode_image(self.preprocess(pil_image.convert("RGB")).unsqueeze(0).to(self.device)).float()
            f = f / f.norm(dim=-1, keepdim=True)
        return f[0].cpu().numpy()
