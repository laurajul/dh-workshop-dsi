"""
Survey Europeana institutions (DATA_PROVIDER facet) with 1000+ images and
write an HTML table with 5 random sample thumbnails per institution.

Usage:
    python scripts/europeana_collection_overview.py [--min-images 1000] [--samples 5]

Output: reference/europeana_collections.html

Notes:
- Thumbnails are Europeana's `edmPreview` (smallest size, ~200px wide).
- Europeana's offset paging is capped at 1000 results, so the random samples are
  drawn from the first 1000 images of each institution.
"""
import argparse
import html
import random
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "reference" / "europeana_collections.html"
BASE_URL = "https://api.europeana.eu/record/v2"
MAX_OFFSET = 1000  # start + rows may not exceed this
PAGE_ROWS = 100

API_KEY_LOCATIONS = [
    PROJECT_ROOT / "notebooks" / "api-key-europeana.txt",
    PROJECT_ROOT / "misc" / "api-key-europeana.txt",
    PROJECT_ROOT / "api-key-europeana.txt",
]


def load_api_key():
    for key_file in API_KEY_LOCATIONS:
        if key_file.exists():
            key = key_file.read_text().strip()
            if key:
                return key
    print("ℹ Using demo API key (limited requests)")
    return "api2demo"


API_KEY = load_api_key()


def get(params, retries=3):
    params = {"wskey": API_KEY, **params}
    for attempt in range(retries):
        try:
            response = requests.get(f"{BASE_URL}/search.json", params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                print(f"❌ Request failed: {e}")
                return None
            time.sleep(2 * (attempt + 1))


def get_providers_with_images(min_images):
    """All DATA_PROVIDER values with TYPE:IMAGE counts, paged via facet offset."""
    providers, offset, page = [], 0, 1000
    while True:
        data = get({
            "query": "*",
            "qf": "TYPE:IMAGE",
            "rows": 0,
            "profile": "facets",
            "facet": "DATA_PROVIDER",
            "f.DATA_PROVIDER.facet.limit": page,
            "f.DATA_PROVIDER.facet.offset": offset,
        })
        fields = []
        if data:
            for facet in data.get("facets", []):
                if facet.get("name") == "DATA_PROVIDER":
                    fields = facet.get("fields", [])
        providers += [(f["label"], f["count"]) for f in fields]
        if len(fields) < page:
            break
        offset += page
    return sorted([p for p in providers if p[1] >= min_images], key=lambda p: -p[1])


def escape_qf(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def sample_thumbnails(provider, total, n):
    """Fetch one random page of images for the provider and sample n previews."""
    rows = min(PAGE_ROWS, total)
    start = random.randint(1, max(1, min(total, MAX_OFFSET) - rows + 1))
    data = get({
        "query": "*",
        "qf": [f'DATA_PROVIDER:"{escape_qf(provider)}"', "TYPE:IMAGE"],
        "rows": rows,
        "start": start,
        "profile": "standard",
    })
    items = [i for i in (data or {}).get("items", []) if i.get("edmPreview")]
    picked = random.sample(items, min(n, len(items)))
    return [
        {
            "thumb": i["edmPreview"][0],
            "link": f"https://www.europeana.eu/item{i['id']}",
            "title": (i.get("title") or ["Untitled"])[0],
        }
        for i in picked
    ]


def render_html(rows, min_images, n):
    body = []
    for provider, total, samples in rows:
        cells = "".join(
            f'<a href="{html.escape(s["link"])}" target="_blank" title="{html.escape(s["title"])}">'
            f'<img src="{html.escape(s["thumb"])}" loading="lazy" alt="{html.escape(s["title"])}"></a>'
            for s in samples
        )
        link = f"https://www.europeana.eu/en/search?query=*&qf=DATA_PROVIDER:%22{requests.utils.quote(provider)}%22&qf=TYPE:IMAGE"
        body.append(
            f'<tr><td class="name"><a href="{html.escape(link)}" target="_blank">{html.escape(provider)}</a></td>'
            f'<td class="num">{total:,}</td><td class="imgs">{cells}</td></tr>'
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Europeana institutions with {min_images:,}+ images</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #ddd; padding: .5rem; vertical-align: middle; text-align: left; }}
th {{ position: sticky; top: 0; background: #fff; }}
td.num {{ text-align: right; white-space: nowrap; }}
td.imgs {{ white-space: nowrap; }}
td.imgs img {{ height: 120px; margin-right: 6px; background: #eee; }}
</style></head><body>
<h1>Europeana institutions with {min_images:,}+ images</h1>
<p>{len(rows)} institutions. {n} random thumbnails each (smallest size). Generated {time.strftime("%Y-%m-%d")}.</p>
<table><thead><tr><th>Institution</th><th>Images</th><th>Samples</th></tr></thead>
<tbody>
{chr(10).join(body)}
</tbody></table></body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-images", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    providers = get_providers_with_images(args.min_images)
    print(f"Found {len(providers)} institutions with >= {args.min_images:,} images")

    rows = []
    for idx, (provider, total) in enumerate(providers, 1):
        print(f"[{idx}/{len(providers)}] {provider} ({total:,})")
        rows.append((provider, total, sample_thumbnails(provider, total, args.samples)))
        time.sleep(0.2)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(render_html(rows, args.min_images, args.samples), encoding="utf-8")
    print(f"✓ Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
