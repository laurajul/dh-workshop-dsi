"""Helper functions for the intro notebook (Europeana section).

The notebook cells only call these functions, so that the cells shown during the presentation stay short.
Everything here is read-only: it queries the public Europeana APIs. The only files written are the
cached counts and exports under data/europeana/.
"""
import csv
import html
import json
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from IPython.display import HTML, display

# ---------------------------------------------------------------- paths and API key

NOTEBOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = NOTEBOOK_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
EUROPEANA_DIR = DATA_DIR / "europeana"
EUROPEANA_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.europeana.eu/record/v2"
API_KEY = "api2demo"                       # shared demo key: enough for the notebook, but rate limited
API_KEY_STATUS = ("Using the shared demo key (limited requests). For your own free key see "
                  "https://pro.europeana.eu/page/get-api and save it to notebooks/api-key-europeana.txt")
for _f in [NOTEBOOK_DIR / "api-key-europeana.txt", PROJECT_ROOT / "misc" / "api-key-europeana.txt",
           PROJECT_ROOT / "api-key-europeana.txt"]:
    if _f.exists():
        _k = _f.read_text().strip()
        if _k and _k != "api2demo":
            API_KEY, API_KEY_STATUS = _k, f"API key loaded from {_f}"
            break

TYPES = ["IMAGE", "TEXT", "SOUND", "VIDEO", "3D"]


# ---------------------------------------------------------------- Search API

def search_raw(**params):
    r = requests.get(f"{BASE_URL}/search.json", params={"wskey": API_KEY, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def facet_counts(facet, page=2000, **extra):
    # Return every (value, count) pair of a facet, following the facet offset until it runs out.
    out, offset = [], 0
    while True:
        data = search_raw(query="*", rows=0, profile="facets", facet=facet,
                          **{f"f.{facet}.facet.limit": page, f"f.{facet}.facet.offset": offset}, **extra)
        fields = next((f["fields"] for f in data.get("facets", []) if f["name"] == facet), [])
        out += [(f["label"], f["count"]) for f in fields]
        if len(fields) < page:
            return out
        offset += page


def facet_pairs(facet, query="*", limit=10, qf=None, **extra):
    data = search_raw(query=query, rows=0, profile="facets", facet=facet, qf=qf, **{f"f.{facet}.facet.limit": limit}, **extra)
    fields = next((f["fields"] for f in data.get("facets", []) if f["name"] == facet), [])
    return data["totalResults"], [(x["label"], x["count"]) for x in fields]


def count(query="*", **kw):
    return search_raw(query=query, rows=0, **kw)["totalResults"]


def search_europeana(query="*", rows=12, reusability="open", qf=None, profile="rich", cursor=None, theme=None):
    """Search the Europeana collection and return the response as a dictionary (None on error).

    query: search text ("*" for all). rows: number of results (max 100). reusability: "open", "restricted",
    "permission" or None. qf: filters as a list, e.g. ["TYPE:IMAGE", "COUNTRY:Netherlands"].
    profile: "standard", "rich" or "facets". cursor: for paging beyond 100 results.
    theme: a thematic collection, e.g. "art", "photography", "manuscripts", or None.
    """
    params = {"wskey": API_KEY, "query": query, "rows": min(rows, 100), "profile": profile}
    if reusability:
        params["reusability"] = reusability
    if qf:
        params["qf"] = qf
    if cursor:
        params["cursor"] = cursor
    if theme:
        params["theme"] = theme
    try:
        response = requests.get(f"{BASE_URL}/search.json", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error searching Europeana: {e}")
        return None


# ---------------------------------------------------------------- reading fields of a record

def get_item_title(item):
    if item.get("title"):
        return item["title"][0] if isinstance(item["title"], list) else item["title"]
    if "dcTitleLangAware" in item:
        for lang in ["en", "nl", "de", "fr", "sv", "def"]:
            if lang in item["dcTitleLangAware"]:
                return item["dcTitleLangAware"][lang][0]
    return "Untitled"


def get_item_creator(item):
    if item.get("dcCreator"):
        return item["dcCreator"][0] if isinstance(item["dcCreator"], list) else item["dcCreator"]
    return "Unknown"


def get_item_year(item):
    if item.get("year"):
        return item["year"][0] if isinstance(item["year"], list) else item["year"]
    return "n.d."


def get_item_preview(item):
    if item.get("edmPreview"):
        return item["edmPreview"][0] if isinstance(item["edmPreview"], list) else item["edmPreview"]
    return None


def get_full_image_url(item):
    if item.get("edmIsShownBy"):
        return item["edmIsShownBy"][0] if isinstance(item["edmIsShownBy"], list) else item["edmIsShownBy"]
    return None


def first_of(v, default=""):
    return (v[0] if isinstance(v, list) and v else v) or default


def show_results(items, numbered=True, size=170):
    # Cards with preview, title, creator, year and institution. Numbered so that one can be picked by number.
    cards = ""
    for n, it in enumerate(items):
        num = f"<b style='color:#BC8F8F'>#{n}</b> " if numbered else ""
        cards += (f"<figure style='margin:0;width:{size}px;font:11px sans-serif'>"
                  f"<img src='{get_item_preview(it) or ''}' style='width:{size}px;height:{size}px;object-fit:cover;background:#D3D3D3'>"
                  f"<figcaption>{num}<b>{html.escape(get_item_title(it)[:60])}</b><br>"
                  f"{html.escape(str(get_item_creator(it))[:40])} ({get_item_year(it)})<br>"
                  f"<i>{html.escape(first_of(it.get('dataProvider'))[:40])}</i></figcaption></figure>")
    display(HTML(f"<div style='display:flex;gap:12px;flex-wrap:wrap'>{cards}</div>"))


# ---------------------------------------------------------------- IIIF manifests

def get_iiif_manifest_url(item):
    """Europeana generates a IIIF manifest for every record, at a predictable address:
    https://iiif.europeana.eu/presentation/{dataset}/{local_id}/manifest
    """
    item_id = item.get("id")
    if not item_id:
        return None
    parts = item_id.strip("/").split("/")
    if len(parts) >= 2:
        return f"https://iiif.europeana.eu/presentation/{parts[0]}/{parts[1]}/manifest"
    return None


def manifest_has_image_service(item):
    # Fetch the item's IIIF manifest and report whether its images are served by an IIIF Image API service.
    url = get_iiif_manifest_url(item) + "?format=3"
    try:
        manifest = requests.get(url, timeout=30).json()
        body = manifest["items"][0]["items"][0]["items"][0]["body"]
        return bool(body.get("service"))
    except Exception:
        return None


def check_manifests(items, workers=6):
    # One manifest check per record, in parallel. Returns a list of True / False / None.
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(manifest_has_image_service, items))


# ---------------------------------------------------------------- the overview of institutions

def collect_overview(total_items):
    result = {"fetched": time.strftime("%Y-%m-%d"), "total_items": total_items, "facets": {}}
    for facet in ["DATA_PROVIDER", "PROVIDER", "COUNTRY"]:
        columns = {"total": facet_counts(facet)}
        for t in TYPES:
            columns[t] = facet_counts(facet, qf=f"TYPE:{t}")
        if facet == "DATA_PROVIDER":
            columns["art"] = facet_counts(facet, theme="art")
            columns["iiif"] = facet_counts(facet, qf="wr_dcterms_isReferencedBy:*")
        result["facets"][facet] = {k: dict(v) for k, v in columns.items()}
        print(f"  {facet}: {len(columns['total']):,} values")
    return result


def _table_rows(overview, facet):
    # One dict per value of the facet, with a count for the total, each type and (for institutions) the Art theme.
    cols = overview["facets"][facet]
    return [{"name": name, **{c: cols[c].get(name, 0) for c in cols}} for name in cols["total"]]


def load_overview(refresh=False):
    """Counts per institution, provider and country. Read from data/europeana/overview_cache.json if present;
    otherwise fetched from the API (about 35 small requests) and saved. Returns (overview, institutions, aggregators, countries)."""
    cache = EUROPEANA_DIR / "overview_cache.json"
    if cache.exists() and not refresh:
        overview = json.loads(cache.read_text())
        print(f"Loaded cached counts from {overview['fetched']}")
        if "iiif" not in overview["facets"]["DATA_PROVIDER"]:      # cache written before this column existed
            overview["facets"]["DATA_PROVIDER"]["iiif"] = dict(facet_counts("DATA_PROVIDER", qf="wr_dcterms_isReferencedBy:*"))
            cache.write_text(json.dumps(overview))
    else:
        print("Fetching counts from the API (about 35 requests) ...")
        overview = collect_overview(search_raw(query="*", rows=0)["totalResults"])
        cache.write_text(json.dumps(overview))
        print("Saved to", cache)
    institutions = _table_rows(overview, "DATA_PROVIDER")
    aggregators = _table_rows(overview, "PROVIDER")
    countries = _table_rows(overview, "COUNTRY")
    print(f"{len(institutions):,} institutions (data providers), {len(aggregators)} providers / aggregators, {len(countries)} countries")
    return overview, institutions, aggregators, countries


# ---------------------------------------------------------------- tables and bars

COLORS = {"IMAGE": "#C0C0C0", "TEXT": "#BC8F8F", "SOUND": "#FF7F50", "VIDEO": "#DC143C", "3D": "#8A2BE2"}
LABELS = {"IMAGE": "Image", "TEXT": "Text", "SOUND": "Sound", "VIDEO": "Video", "3D": "3D"}


def mix_bar(row, width=170):
    typed = sum(row[t] for t in TYPES) or 1
    parts = "".join(
        f"<span title='{LABELS[t]}: {row[t]:,} ({row[t] / typed:.0%})' "
        f"style='display:inline-block;height:12px;width:{max(row[t] / typed * width, 0):.1f}px;background:{COLORS[t]};margin-right:{1 if row[t] else 0}px'></span>"
        for t in TYPES)
    return f"<div style='white-space:nowrap;line-height:0'>{parts}</div>"


def show_table(rows, sort_by="total", n=20, first_col="Institution", art=False, iiif=False, min_total=0):
    rows = [r for r in rows if r["total"] >= min_total]
    rows = sorted(rows, key=lambda r: r[sort_by], reverse=True)[:n]
    head = (f"<th style='text-align:left'>{first_col}</th><th>Total</th>"
            + "".join(f"<th>{LABELS[t]}</th>" for t in TYPES) + ("<th>Art theme</th>" if art else "")
            + ("<th>IIIF-linked</th>" if iiif else "") + "<th style='text-align:left'>Media mix</th>")
    body = ""
    for r in rows:
        cells = "".join(f"<td style='text-align:right'>{r[t]:,}</td>" if r[t] else "<td style='text-align:right;color:#C0C0C0'>–</td>" for t in TYPES)
        body += (f"<tr><td>{html.escape(r['name'])}</td><td style='text-align:right'><b>{r['total']:,}</b></td>{cells}"
                 + (f"<td style='text-align:right'>{r['art']:,}</td>" if art else "")
                 + (f"<td style='text-align:right'>{r['iiif']:,}</td>" if iiif else "") + f"<td>{mix_bar(r)}</td></tr>")
    legend = " &nbsp; ".join(f"<span style='display:inline-block;width:10px;height:10px;background:{COLORS[t]}'></span> {LABELS[t]}" for t in TYPES)
    display(HTML(f"<div style='font:13px sans-serif;margin-bottom:6px'>{legend}</div>"
                 f"<table style='font:13px sans-serif'><tr>{head}</tr>{body}</table>"))


def century_label(c):
    suffix = "th" if 10 <= c % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(c % 10, "th")
    return f"{c}{suffix} c."


def bar_table(pairs, total, title, label_fmt=lambda x: x):
    rows = "".join(
        f"<tr><td style='padding-right:10px'>{html.escape(str(label_fmt(k)))}</td><td style='text-align:right;padding-right:8px'>{v:,}</td>"
        f"<td><div style='background:#BC8F8F;height:10px;width:{max(v / total * 160, 1):.0f}px'></div></td></tr>" for k, v in pairs)
    return f"<div><b>{title}</b><table style='font:12px sans-serif'>{rows}</table></div>"


def short_rights(u):
    return u.rstrip("/").split("/")[-2] + " " + u.rstrip("/").split("/")[-1] if ("creativecommons" in u or "rightsstatements" in u) else u


def institution_preview(name, n_samples=12):
    # A quick profile of one institution: media types, rights, period, frequent creators and a few sample images.
    flt = f'DATA_PROVIDER:"{name}"'
    data = search_raw(query="*", rows=0, qf=flt, profile="facets", facet="TYPE,RIGHTS,YEAR,proxy_dc_creator",
                      **{"f.TYPE.facet.limit": 6, "f.RIGHTS.facet.limit": 5, "f.YEAR.facet.limit": 2000, "f.proxy_dc_creator.facet.limit": 8})
    total = data["totalResults"]
    fac = {f["name"]: [(x["label"], x["count"]) for x in f["fields"]] for f in data.get("facets", [])}

    centuries = {}
    for y, c in fac.get("YEAR", []):
        if y.isdigit():
            centuries[int(y) // 100 + 1] = centuries.get(int(y) // 100 + 1, 0) + c
    has_images = any(t == "IMAGE" for t, _ in fac.get("TYPE", []))

    start = random.randint(1, max(1, min(total, 1000) - n_samples + 1))
    sample_filter = [flt, "TYPE:IMAGE"] if has_images else [flt]
    sample = search_raw(query="*", rows=n_samples, start=start, qf=sample_filter, profile="standard").get("items", [])

    panels = "".join([
        bar_table(fac.get("TYPE", []), total, "Media types"),
        bar_table(fac.get("RIGHTS", []), total, "Rights (top 5)", short_rights),
        bar_table(sorted(centuries.items()), max(centuries.values(), default=1), "Items by century (dated items)", century_label),
        bar_table(fac.get("proxy_dc_creator", []), max((c for _, c in fac.get("proxy_dc_creator", [])), default=1), "Most frequent creators"),
    ])
    thumbs = "".join(
        f"<figure style='margin:0;width:150px;font:11px sans-serif'><img src='{(it.get('edmPreview') or [''])[0]}' style='width:150px;height:150px;object-fit:cover;background:#D3D3D3'>"
        f"<figcaption>{html.escape(get_item_title(it)[:70])}</figcaption></figure>" for it in sample)
    display(HTML(f"<h4 style='font-family:sans-serif'>{html.escape(name)}: {total:,} items</h4>"
                 f"<div style='display:flex;gap:28px;flex-wrap:wrap'>{panels}</div>"
                 f"<div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:12px'>{thumbs}</div>"))


# ---------------------------------------------------------------- export

def write_csv(rows, name):
    path = EUROPEANA_DIR / name
    cols = ["name", "total"] + TYPES + (["art", "iiif"] if "art" in rows[0] else [])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["total"], reverse=True))
    return path


def export_metadata(query, qf=None, theme=None, pages=3, rows=100):
    # Collect records page by page with a cursor and return them as a list of flat dictionaries.
    records, cursor = [], "*"
    for _ in range(pages):
        res = search_europeana(query=query, rows=rows, qf=qf, theme=theme, reusability="open", profile="standard", cursor=cursor)
        if not res or not res.get("items"):
            break
        for it in res["items"]:
            records.append({
                "id": it.get("id"), "title": get_item_title(it), "creator": get_item_creator(it), "year": get_item_year(it),
                "institution": first_of(it.get("dataProvider")), "provider": first_of(it.get("provider")),
                "country": first_of(it.get("country")), "type": it.get("type"), "rights": it.get("rights", [""])[0],
                "landing_page": first_of(it.get("edmIsShownAt")), "preview": get_item_preview(it) or "",
            })
        cursor = res.get("nextCursor")
        if not cursor:
            break
    return records
