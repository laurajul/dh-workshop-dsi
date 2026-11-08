#!/usr/bin/env python3
"""
Build the workshop dataset (instructor use): CLIP embeddings plus a list of image URLs. No images are stored.

Four stages, run in this order:

    python scripts/build_dataset.py plan      # count what the selection contains and estimate the effort
    python scripts/build_dataset.py harvest   # collect metadata records from the Europeana Search API (resumable)
    python scripts/build_dataset.py embed     # stream each image into CLIP and keep only the vector (shardable)
    python scripts/build_dataset.py merge     # combine the shard files into the final dataset

`plan` and `harvest` run on any machine with an API key. `embed` is the heavy stage and is meant for a cluster
(GPU if available): copy `harvest/records.jsonl` and the CLIP weights there, run one `embed` job per shard,
copy the `parts` back and run `merge`. Example SLURM array job (200 shards):

    #SBATCH --array=0-199%10 --gres=gpu:1 --cpus-per-task=16
    python build_dataset.py embed --out $DATA --shards 200 --models $DATA/models --workers 32 --thumb-rate 5
    # SLURM_ARRAY_TASK_ID selects the shard; "%10" runs at most 10 shards at once, so the thumbnail service
    # receives about 10 x 5 = 50 requests per second in total.

Final output (default --out data/DSI-Workshop), the files participants use:

    metadata.csv                   one row per image, same order as the embeddings
    embeddings/clip_vit_b32.npz    ids, vectors (N x 512, L2-normalised, float16), model

Working files: harvest/records.jsonl, harvest/done_institutions.txt, embeddings/parts/, metadata_parts/.

Selection
    Records that are images (TYPE:IMAGE, so no books or other text), belong to Europeana's thematic collection "art"
    (--theme art, the default; --theme "" for all themes), have a media file (edmIsShownBy) and are openly reusable.
    The Art collection is a theme, not a media type: it cuts across types, and its text items (books, manuscripts) are
    left out by the image filter. Use a fresh --out folder when you change the theme; harvest refuses to mix them.

    Size budget (recommended): --budget-gb 9.5 limits metadata.csv plus the embeddings to that size. A row costs
    about 1.5 KB (about 0.5 KB metadata, 1 KB float16 vector), so 9.5 GB is roughly 6 million images. The budget is
    spread by the same rule everywhere: an institution contributes all of its records if it has fewer than a cap,
    and exactly `cap` records otherwise, with the largest cap that fits (the cap is printed by `plan`).
    `harvest` collects --margin (default 1.1) times the budget, and `merge --max-gb 9.5` trims to the real size
    using the actual file sizes, taking each institution's records in order of Europeana ID.

    Without a budget: institutions with at least --big-threshold records contribute --per-institution of them
    (0 = all), smaller ones contribute all of theirs (optionally capped with --small-cap, at least --min-items).

Images (fetched only while embedding, then discarded)
    If the media URL is a IIIF Image API URL, the small image (`!448,448`) is requested from that service. If that
    fails, Europeana's thumbnail service (max. 400 px wide, no API key needed) is used. The URL that worked is
    stored as `small_image_url`, so participants can fetch exactly the same small image later. `iiif_service` is
    kept only if the service answered. `full_image_url` is the original file.

Notes
    * Europeana publishes no daily quota. Staff have mentioned about 120 requests per 10 seconds, and the fair-use
      policy allows limits to change, so harvest throttles itself (--rate, default 8 requests/s) and backs off on
      HTTP 429. Keys must not be shared. For very large volumes Europeana also offers dumps via FTP and OAI-PMH.
    * Records come in Europeana's default order within an institution (cursor paging cannot be randomised), so a
      large institution's sample reflects its own result order.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import threading
import time
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API = "https://api.europeana.eu/record/v2/search.json"
THUMB = "https://api.europeana.eu/thumbnail/v2/url.json"
BASE_FILTERS = ["TYPE:IMAGE", "provider_aggregation_edm_isShownBy:*"]
KEY_FILES = [PROJECT_ROOT / "notebooks" / "api-key-europeana.txt", PROJECT_ROOT / "misc" / "api-key-europeana.txt",
             PROJECT_ROOT / "api-key-europeana.txt"]

# A IIIF Image API request URL: {service}/{region}/{size}/{rotation}/{quality}.{format}
IIIF_URL = re.compile(
    r"^(https?://.+?)/(?:full|square|pct:[\d.,]+|\d+,\d+,\d+,\d+)/[^/]+/!?\d+(?:\.\d+)?/"
    r"(?:default|color|colour|gray|grey|bitonal|native)\.(?:jpe?g|png|webp|tiff?|gif)(?:\?.*)?$", re.I)

META_BYTES_PER_ROW = 520        # measured: about 500 bytes per metadata.csv row
EMB_BYTES_PER_ROW = 1000        # measured: about 970 bytes per row in the compressed float16 .npz, including the id

FIELDS = ["id", "institution", "provider", "country", "type", "title", "creator", "year", "rights", "landing_page",
          "full_image_url", "small_image_url", "iiif_service", "iiif_manifest", "image_source"]

_local = threading.local()


def session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = "dh-workshop-dataset-builder"
    return _local.s


class RateLimiter:
    # At most `rate` calls per second across all threads of this process.
    def __init__(self, rate):
        self.interval, self.next, self.lock = 1.0 / rate, 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next - now)
            self.next = max(now, self.next) + self.interval
        if delay:
            time.sleep(delay)


LIMITER = RateLimiter(8)
THUMB_LIMITER = None            # per-process limiter for Europeana's thumbnail service, set in each embed worker


def set_thumb_rate(rate):
    global THUMB_LIMITER
    THUMB_LIMITER = RateLimiter(rate) if rate else None


def check_key(key, source):
    # A placeholder such as "..." or "<your key>" would only produce a confusing HTTP 401 later.
    if not re.fullmatch(r"[A-Za-z0-9]{4,40}", key):
        raise SystemExit(f"The API key from {source} does not look like a Europeana key (letters and digits only; "
                         f"got {len(key)} characters starting {key[:3]!r}). Set your real key, e.g. "
                         f"export EUROPEANA_API_KEY=yourkey, or put it in misc/api-key-europeana.txt.")
    return key


def load_key(arg):
    if arg:
        return check_key(arg.strip(), "--api-key")
    if os.environ.get("EUROPEANA_API_KEY", "").strip():
        return check_key(os.environ["EUROPEANA_API_KEY"].strip(), "EUROPEANA_API_KEY")
    for f in KEY_FILES:
        if f.exists() and f.read_text().strip():
            return check_key(f.read_text().strip(), str(f))
    print("! No API key found, using the demo key (heavily rate limited). See --api-key.", file=sys.stderr)
    return "api2demo"


def redact(text):
    return re.sub(r"(wskey=)[^&\s]+", r"\1***", str(text))      # error messages contain the URL, and with it the key


def get_json(params, retries=5):
    last = ""
    for attempt in range(retries):
        LIMITER.wait()
        try:
            r = session().get(API, params=params, timeout=60)
        except requests.RequestException as e:
            last = redact(e)
        else:
            if r.status_code in (401, 403):
                raise SystemExit(f"Europeana rejected the API key (HTTP {r.status_code}). Check EUROPEANA_API_KEY or "
                                 "misc/api-key-europeana.txt. Keys are free at https://pro.europeana.eu/page/get-api; "
                                 "the shared demo key is api2demo.")
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep((15 if r.status_code == 429 else 3) * (attempt + 1)); continue
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code} from the Europeana API")
            return r.json()
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Europeana API request failed after {retries} attempts: {last}")


def first(v, default=""):
    if isinstance(v, list):
        v = v[0] if v else default
    return v if v not in (None, "") else default


# ------------------------------------------------------------------ plan
def search_params(theme):
    # Parameters that every selection query shares (the institution is added per query).
    p = {"qf": list(BASE_FILTERS), "reusability": "open"}
    if theme:
        p["theme"] = theme
    return p


def institution_counts(key, theme):
    out, offset, page = {}, 0, 2000
    while True:
        d = get_json({"wskey": key, "query": "*", "rows": 0, "profile": "facets", "facet": "DATA_PROVIDER",
                      "f.DATA_PROVIDER.facet.limit": page, "f.DATA_PROVIDER.facet.offset": offset,
                      **search_params(theme)})
        fields = next((f["fields"] for f in d.get("facets", []) if f["name"] == "DATA_PROVIDER"), [])
        out.update({f["label"]: f["count"] for f in fields})
        if len(fields) < page:
            return out
        offset += page


def water_fill(sizes, budget):
    # The largest cap c such that sum(min(n, c)) <= budget.
    lo, hi = 0, max(sizes)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if sum(min(n, mid) for n in sizes) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return lo


def selection(args, key):
    counts = institution_counts(key, args.theme)
    chosen = {}
    if args.budget_gb:
        rows = int(args.budget_gb * 1e9 / (META_BYTES_PER_ROW + EMB_BYTES_PER_ROW) * args.margin)
        eligible = {n: c for n, c in counts.items() if c >= args.min_items}
        if args.max_institutions:                                 # for tests: the N largest institutions
            eligible = dict(sorted(eligible.items(), key=lambda kv: -kv[1])[:args.max_institutions])
        args.cap = water_fill(list(eligible.values()), rows)
        if args.cap < 1:
            raise SystemExit(f"The budget ({args.budget_gb:g} GB, about {rows:,} records) is too small for one record from each of "
                             f"{len(eligible):,} institutions. Raise --budget-gb, or limit --max-institutions / raise --min-items.")
        return counts, {n: min(c, args.cap) for n, c in eligible.items()}
    args.cap = None
    for name, n in counts.items():
        if n >= args.big_threshold:
            chosen[name] = min(n, args.per_institution) if args.per_institution else n
        elif n >= args.min_items:
            chosen[name] = min(n, args.small_cap) if args.small_cap else n
    if args.max_institutions:
        chosen = dict(sorted(chosen.items(), key=lambda kv: -kv[1])[:args.max_institutions])
    return counts, chosen


def cmd_plan(args):
    key = load_key(args.api_key)
    counts, chosen = selection(args, key)
    total = sum(chosen.values())
    big = [n for n in chosen if (counts[n] > args.cap if args.cap else counts[n] >= args.big_threshold)]
    requests_needed = sum((n + 99) // 100 for n in chosen.values())
    print(f"Theme: {args.theme or 'all'}. Institutions with open image records: {len(counts):,} ({sum(counts.values()):,} records)")
    if args.cap:
        print(f"Budget {args.budget_gb:g} GB x margin {args.margin:g}: each institution contributes at most {args.cap:,} records")
    print(f"Selected: {len(chosen):,} institutions ({len(big)} capped, {len(chosen) - len(big):,} taken completely)")
    print(f"Images to embed: {total:,}")
    print(f"Harvest: ~{requests_needed:,} Search API requests, ~{requests_needed / args.rate / 3600:,.1f} h at {args.rate:g} requests/s")
    print(f"Embed: ~{total * 30 / 1e6:,.0f} GB of images streamed through (about 30 KB each, nothing stored)")
    print(f"  final size (metadata.csv + float16 embeddings): ~{total * (META_BYTES_PER_ROW + EMB_BYTES_PER_ROW) / 1e9:,.1f} GB "
          f"(`merge --max-gb` trims the harvested margin away)")
    print(f"  shards of 20,000 images: {(total + 19_999) // 20_000:,}")
    print("\nLargest contributions:")
    for name, n in sorted(chosen.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>9,}  {name}")


# ------------------------------------------------------------------ harvest
def record_from_item(it):
    shown_by = first(it.get("edmIsShownBy"))
    m = IIIF_URL.match(shown_by)
    item_id = it["id"]
    return {
        "id": item_id,
        "institution": first(it.get("dataProvider")),
        "provider": first(it.get("provider")),
        "country": first(it.get("country")),
        "type": it.get("type", ""),
        "title": first(it.get("title"), "Untitled"),
        "creator": first(it.get("dcCreator")),
        "year": first(it.get("year")),
        "rights": first(it.get("rights")),
        "landing_page": first(it.get("edmIsShownAt")),
        "full_image_url": shown_by,
        "iiif_service": m.group(1) if m else "",          # detected from the URL; verified in the embed stage
    }


def harvest_institution(key, name, limit, theme):
    records, cursor = [], "*"
    while not limit or len(records) < limit:
        rows = 100 if not limit else min(100, limit - len(records))
        q = search_params(theme)
        q["qf"].append(f'DATA_PROVIDER:"{name}"')
        d = get_json({"wskey": key, "query": "*", "rows": rows, "profile": "standard", "cursor": cursor, **q})
        items = d.get("items", [])
        if not items:
            break
        records += [record_from_item(it) for it in items if first(it.get("edmIsShownBy"))]
        cursor = d.get("nextCursor")
        if not cursor:
            break
    return records


def cmd_harvest(args):
    key = load_key(args.api_key)
    out = Path(args.out)
    (out / "harvest").mkdir(parents=True, exist_ok=True)
    rec_file, done_file = out / "harvest" / "records.jsonl", out / "harvest" / "done_institutions.txt"
    config_file = out / "harvest" / "config.json"
    config = {"theme": args.theme, "filters": BASE_FILTERS}
    if config_file.exists() and json.loads(config_file.read_text()) != config:
        raise SystemExit(f"{out} was harvested with other settings ({config_file.read_text()}). Use a fresh --out folder.")
    if not config_file.exists() and (rec_file.exists() or done_file.exists()):
        config_file.write_text(json.dumps({"theme": "", "filters": BASE_FILTERS}))      # older harvest: no theme filter
        if json.loads(config_file.read_text()) != config:
            raise SystemExit(f"{out} contains an earlier harvest without a theme filter. Use a fresh --out folder.")
    config_file.write_text(json.dumps(config))
    for f in (rec_file, done_file):                          # a job killed mid-write can leave a last line without newline
        if f.exists() and f.stat().st_size and not f.read_bytes()[-1:] == b"\n":
            with open(f, "ab") as fh:
                fh.write(b"\n")
    done = set(done_file.read_text(encoding="utf-8").splitlines()) if done_file.exists() else set()
    _, chosen = selection(args, key)
    assert all(c > 0 for c in chosen.values()), "internal error: an institution has a limit of 0"
    todo = [(n, c) for n, c in sorted(chosen.items(), key=lambda kv: -kv[1]) if n not in done]
    print(f"{len(chosen):,} institutions selected, {len(done):,} already done, {len(todo):,} to harvest")

    lock = threading.Lock()
    n_records = 0
    with open(rec_file, "a", encoding="utf-8") as rf, open(done_file, "a", encoding="utf-8") as df, \
            ThreadPoolExecutor(args.workers) as ex:
        futures = {ex.submit(harvest_institution, key, n, c, args.theme): n for n, c in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            name = futures[fut]
            try:
                recs = fut.result()
            except Exception as e:
                print(f"  ! {name}: {e}", file=sys.stderr); continue
            with lock:
                rf.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)
                df.write(name + "\n"); rf.flush(); df.flush()
            n_records += len(recs)
            if i % 25 == 0 or len(recs) >= 5000:
                print(f"  [{i}/{len(todo)}] {name}: {len(recs):,} records ({n_records:,} total)")
    print(f"Harvest finished: {n_records:,} new records in {rec_file}")


# ------------------------------------------------------------------ embed
SOURCES = {0: "", 1: "iiif", 2: "thumbnail"}


def small_url(rec, source):
    if source == 1:
        return f"{rec['iiif_service']}/full/!448,448/0/default.jpg"
    return f"{THUMB}?uri={requests.utils.quote(rec['full_image_url'], safe='')}&size=w400&type=IMAGE"


def fetch_small(rec, min_side=32):
    # Returns (PIL image, source code) or (None, 0). The IIIF service is tried first, then the thumbnail service.
    from PIL import Image
    for source in ((1,) if rec["iiif_service"] else ()) + (2,):
        for attempt in range(3):
            try:
                if source == 2 and THUMB_LIMITER:
                    THUMB_LIMITER.wait()
                r = session().get(small_url(rec, source), timeout=45)
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(3 * (attempt + 1)); continue
                if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
                    break
                im = Image.open(BytesIO(r.content)).convert("RGB")
                if min(im.size) >= min_side:
                    return im, source
                break
            except Exception:
                time.sleep(1 + attempt)
    return None, 0


def set_thumb_rate_worker(rate, _worker_id):
    set_thumb_rate(rate)


def record_shard(rec_id, shards):
    return int(hashlib.md5(rec_id.encode()).hexdigest()[:8], 16) % shards


def find_model_dir(args):
    for c in [args.models, Path(args.out) / "models", Path(args.out) / "models" / "CLIP", PROJECT_ROOT / "models" / "CLIP"]:
        if c and (Path(c) / "ViT-B-32.pt").exists():
            return Path(c)
    return Path(args.models or Path(args.out) / "models")        # clip will download the weights here


def cmd_embed(args):
    import numpy as np
    import torch
    import clip

    out = Path(args.out)
    shard = args.shard if args.shard is not None else int(os.environ.get("SLURM_ARRAY_TASK_ID", 0))
    shards = args.shards
    assert 0 <= shard < shards, f"shard {shard} out of range for {shards} shards"
    part = f"{shard:05d}_of_{shards:05d}"
    emb_file = out / "embeddings" / "parts" / f"part_{part}.npz"
    meta_file = out / "metadata_parts" / f"part_{part}.csv"
    if emb_file.exists() and meta_file.exists():
        print(f"Shard {part} already done."); return

    records, n_lines = {}, 0
    for line in open(out / "harvest" / "records.jsonl", encoding="utf-8"):
        n_lines += 1
        try:
            r = json.loads(line)
        except ValueError:                                       # the half-written line of a harvest that was killed
            continue
        if record_shard(r["id"], shards) == shard:               # keep only this shard's records in memory
            records[r["id"]] = r                                 # de-duplicate by Europeana ID
    rows = sorted(records.values(), key=lambda r: r["id"])
    print(f"Shard {part}: {len(rows):,} of {n_lines:,} harvested records")
    if not rows:
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_dir = find_model_dir(args)
    model, preprocess = clip.load("ViT-B/32", device=device, download_root=str(model_dir))
    model.eval()
    print(f"CLIP ViT-B/32 on {device}, weights in {model_dir}")

    class Remote(torch.utils.data.Dataset):
        def __len__(self): return len(rows)
        def __getitem__(self, i):
            im, source = fetch_small(rows[i])
            if im is None:
                return torch.zeros(3, 224, 224), i, 0
            return preprocess(im), i, source

    # Every worker process throttles itself, so one job sends about --thumb-rate thumbnail requests per second.
    per_worker = args.thumb_rate / max(args.workers, 1) if args.thumb_rate else 0
    set_thumb_rate(per_worker)
    loader = torch.utils.data.DataLoader(Remote(), batch_size=args.batch_size, num_workers=args.workers,
                                         prefetch_factor=4 if args.workers else None,
                                         worker_init_fn=partial(set_thumb_rate_worker, per_worker))
    dtype = np.float32 if args.float32 else np.float16
    vectors = np.zeros((len(rows), 512), dtype=dtype)
    source_of = np.zeros(len(rows), dtype=np.int8)
    t0 = time.time()
    with torch.no_grad():
        for n, (batch, idx, source) in enumerate(loader, 1):
            f = model.encode_image(batch.to(device)).float()
            f = f / f.norm(dim=-1, keepdim=True)
            vectors[idx.numpy()] = f.cpu().numpy().astype(dtype)
            source_of[idx.numpy()] = source.numpy()
            if n % 10 == 0:
                done = min(n * args.batch_size, len(rows))
                print(f"  {done:,}/{len(rows):,}  {done / (time.time() - t0):.1f} img/s", flush=True)

    keep = np.flatnonzero(source_of > 0)
    print(f"  {len(keep):,} embedded, {len(rows) - len(keep):,} without a usable image "
          f"({int((source_of == 1).sum()):,} via IIIF, {int((source_of == 2).sum()):,} via thumbnail)")
    emb_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_meta, tmp_emb = meta_file.with_name(meta_file.name + ".tmp"), emb_file.with_name(emb_file.name + ".tmp")
    with open(tmp_meta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for i in keep:
            r, s = rows[i], int(source_of[i])
            w.writerow({**r, "small_image_url": small_url(r, s), "image_source": SOURCES[s],
                        "iiif_service": r["iiif_service"] if s == 1 else "",
                        "iiif_manifest": f"https://iiif.europeana.eu/presentation{r['id']}/manifest" if s == 1 else ""})
    with open(tmp_emb, "wb") as f:
        np.savez_compressed(f, ids=np.array([rows[i]["id"] for i in keep]), vectors=vectors[keep])
    os.replace(tmp_emb, emb_file)                                # a part only exists once it is complete
    os.replace(tmp_meta, meta_file)
    print(f"Saved {emb_file} and {meta_file}")


# ------------------------------------------------------------------ merge
def choose_rows(parts_meta, budget_bytes, emb_bytes):
    # Water-filling on real sizes: the largest per-institution cap whose kept rows fit the budget.
    # parts_meta: list (per part) of lists of (id, institution, row_bytes). Returns the cap and a keep mask per part.
    from bisect import bisect_right
    from itertools import accumulate
    by_inst = {}
    for pi, rows in enumerate(parts_meta):
        for ri, (rid, inst, nbytes) in enumerate(rows):
            by_inst.setdefault(inst, []).append((rid, nbytes + emb_bytes, pi, ri))
    prefix = {}
    for inst, rows in by_inst.items():
        rows.sort()                                             # in order of Europeana ID
        prefix[inst] = list(accumulate(r[1] for r in rows))

    def cost(cap):
        return sum(pf[min(cap, len(pf)) - 1] for pf in prefix.values() if pf and cap)

    hi = max(len(r) for r in by_inst.values())
    if cost(hi) <= budget_bytes:
        cap = hi
    else:
        lo = 0
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if cost(mid) <= budget_bytes else (lo, mid - 1)
        cap = lo
    keep = [[False] * len(rows) for rows in parts_meta]
    for rows in by_inst.values():
        for _, _, pi, ri in rows[:cap]:
            keep[pi][ri] = True
    return cap, keep


def cmd_merge(args):
    import numpy as np
    out = Path(args.out)
    emb_parts = sorted((out / "embeddings" / "parts").glob("part_*.npz"))
    meta_parts = sorted((out / "metadata_parts").glob("part_*.csv"))
    assert emb_parts and len(emb_parts) == len(meta_parts), "missing or mismatched part files"

    # pass 1: row sizes from the metadata parts only (cheap)
    parts_meta = []
    for mp in meta_parts:
        rows = list(csv.DictReader(open(mp, encoding="utf-8")))
        sizes = [len(",".join(r.values())) + 2 for r in rows]
        parts_meta.append([(r["id"], r["institution"], n) for r, n in zip(rows, sizes)])
    total = sum(len(p) for p in parts_meta)
    if args.max_gb:
        cap, keep = choose_rows(parts_meta, args.max_gb * 1e9, EMB_BYTES_PER_ROW)
        print(f"Trimming {total:,} rows to fit {args.max_gb:g} GB: at most {cap:,} per institution")
    else:
        keep = [[True] * len(p) for p in parts_meta]
    n_keep = sum(sum(k) for k in keep)

    # pass 2: write metadata.csv and fill the vector array part by part
    vectors, ids, at = None, [], 0
    with open(out / "metadata.csv", "w", newline="", encoding="utf-8") as mf:
        w = csv.DictWriter(mf, fieldnames=FIELDS); w.writeheader()
        for ep, mp, k in zip(emb_parts, meta_parts, keep):
            z = np.load(ep)
            rows = list(csv.DictReader(open(mp, encoding="utf-8")))
            assert [r["id"] for r in rows] == list(z["ids"]), f"{ep.name} and {mp.name} are not aligned"
            sel = [i for i, flag in enumerate(k) if flag]
            if vectors is None:
                vectors = np.empty((n_keep, z["vectors"].shape[1]), dtype=z["vectors"].dtype)
            vectors[at:at + len(sel)] = z["vectors"][sel]
            ids += [rows[i]["id"] for i in sel]
            w.writerows(rows[i] for i in sel)
            at += len(sel)
    (out / "embeddings").mkdir(exist_ok=True)
    np.savez_compressed(out / "embeddings" / "clip_vit_b32.npz", ids=np.array(ids), vectors=vectors, model="ViT-B/32")

    sizes = {f: (out / f).stat().st_size for f in ("metadata.csv", "embeddings/clip_vit_b32.npz")}
    print(f"Merged {len(emb_parts)} parts: {n_keep:,} images, vectors {vectors.shape} {vectors.dtype}")
    human = lambda n: f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.2f} MB"
    print(f"  metadata.csv {human(sizes['metadata.csv'])} + embeddings {human(sizes['embeddings/clip_vit_b32.npz'])} "
          f"= {human(sum(sizes.values()))}")
    if args.max_gb and sum(sizes.values()) > args.max_gb * 1e9:
        print(f"  ! over the {args.max_gb:g} GB limit: run merge again with a slightly smaller --max-gb", file=sys.stderr)


# ------------------------------------------------------------------ cli
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=["plan", "harvest", "embed", "merge"])
    p.add_argument("--out", default=str(PROJECT_ROOT / "data" / "DSI-Workshop"))
    p.add_argument("--api-key")
    p.add_argument("--theme", default="art", help='Europeana thematic collection to take records from (default: "art"; "" = all themes)')
    p.add_argument("--per-institution", type=int, default=10_000, help="records taken from each large institution (0 = all)")
    p.add_argument("--big-threshold", type=int, default=10_000, help="institutions with at least this many records count as large")
    p.add_argument("--min-items", type=int, default=1, help="skip smaller institutions with fewer records than this")
    p.add_argument("--small-cap", type=int, help="optional cap on records taken from each smaller institution (default: all)")
    p.add_argument("--max-institutions", type=int, help="only the N largest selected institutions (for tests)")
    p.add_argument("--rate", type=float, default=8, help="Search API requests per second, all threads together")
    p.add_argument("--workers", type=int, default=None, help="harvest: parallel institutions; embed: download/preprocess workers")
    p.add_argument("--thumb-rate", type=float, default=5, help="embed: thumbnail requests per second for ONE job (0 = unlimited); "
                   "the total is this times the number of jobs running at once")
    p.add_argument("--shard", type=int, help="embed: shard number (default: $SLURM_ARRAY_TASK_ID, else 0)")
    p.add_argument("--shards", type=int, default=1, help="embed: total number of shards")
    p.add_argument("--models", help="folder containing ViT-B-32.pt (default: <out>/models, then models/CLIP)")
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--float32", action="store_true", help="embed: store float32 instead of float16 (double the size)")
    p.add_argument("--budget-gb", type=float, help="plan/harvest: limit metadata.csv + embeddings to this size, e.g. 9.5")
    p.add_argument("--margin", type=float, default=1.1, help="plan/harvest: harvest this factor more than the budget; merge trims")
    p.add_argument("--max-gb", type=float, help="merge: trim to this size (metadata.csv + embeddings), e.g. 9.5")
    args = p.parse_args()
    if args.workers is None:
        args.workers = {"harvest": 4, "embed": 16}.get(args.stage, 4)
    global LIMITER
    LIMITER = RateLimiter(args.rate)
    {"plan": cmd_plan, "harvest": cmd_harvest, "embed": cmd_embed, "merge": cmd_merge}[args.stage](args)


if __name__ == "__main__":
    main()
