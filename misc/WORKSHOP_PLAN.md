# Workshop plan

Working brief for the restructured workshop. Notebooks are numbered in teaching order.

## Principles

- Simple and descriptive. Each notebook shows what a technology allows, then hands over a small exercise.
- Efficient by design: IIIF (or Europeana's thumbnail service) gives images at the size a model needs, so nothing large is downloaded unless someone looks at one image closely.
- Participants do not need a GPU or a big download. Heavy work (harvesting, embeddings) is done once by the instructor. Only vectors and links are shared. Images are fetched by participants, only for the results they look at.

## Notebooks

### 01 `01_intro_iiif_europeana.ipynb`
One introductory notebook with two sections (it replaces the former `00_welcome`, `01_iiif_overview` and `02_europeana_api_and_data`). A short welcome and setup check come first.

**IIIF** (starts in the browser)
- Murten terapixel panorama first: participants get the URL and the steps to open the developer tools (Network tab, filter Img, pan and zoom) and read the tile requests. The idea of starting from the Network tab follows the IIIF intro videos of the ZB Zürich (ZB-Lab).
- What IIIF is, why it matters, where to find it, how to use it.
- The Book of Hours (Fragmentarium F-mp8l, 61 canvases, 16 ranges): the raw manifest JSON in the browser and as a printed outline (`show_outline`), with the schema of manifest, canvases, images and ranges. e-manuscripta link and a slot for its manifest URL.
- An annotated manuscript on e-rara (text layer, the story of the woman and her defender: instructor notes still to complete).
- How it works behind the scenes: Presentation API, Image API URLs, tiles, annotations, Mirador.
- Hands-on: change an image by editing its URL.

**Europeana** (distant reading of the aggregator)
- How data reaches Europeana, the Search API, who contributes, routes and countries, which institutions name a IIIF manifest, one institution in detail, filters beyond the website, one record and its IIIF manifest.
- Hands-on: find an object with a IIIF manifest.

Appendix: the details of both sections (Switzerland, structure of a manifest, Image API, facets, metadata export). Keyword search is kept short, because the Europeana website already does it well. The emphasis is on aggregate questions and on exporting metadata as a dataset.

### 03 `03_clip_search.ipynb`  (semantic search; how to cover it is still open)
Compare a participant's own query against a shared, precomputed dataset.
- Load `metadata.csv` and the embeddings from `data/DSI-Workshop/`, the CLIP model from `data/DSI-Workshop/models/`.
- Text query to ranked images; filters as boolean masks (institution, country, period); where do the results come from; image query ("more like this" or an uploaded file).
- The images of the results are fetched on demand from `small_image_url` and cached locally.
- "Look closely": a larger version or a detail from the institution's IIIF image service when one worked, otherwise a full download of the original. The cell reports the bytes transferred.

## Instructor build script

`scripts/build_dataset.py`, four stages:

| Stage | Where | What |
|---|---|---|
| `plan` | anywhere | counts the selection, estimates harvest time and sizes |
| `harvest` | anywhere with an API key | metadata records from the Search API into `harvest/records.jsonl` (resumable, throttled to `--rate` requests/s) |
| `embed` | cluster, one job per `--shard` | streams each small image into CLIP and keeps only the vector and the URL that worked; no images are stored |
| `merge` | anywhere | joins the shard files into `metadata.csv` and `embeddings/clip_vit_b32.npz` |

Cluster: `scripts/slurm/` has batch scripts for all three heavy stages (`harvest.sbatch`, `embed.sbatch` submitted by `submit_embed.sh`, `merge.sbatch`) and a README with setup, a 10,000-image test run and recovery steps.

Selection: open-licence image records with a media file from Europeana's Art thematic collection (`--theme art`, the default; images only, so no books or other text). Options: `--budget-gb`, or the manual caps `--per-institution` (0 = all), `--big-threshold`, `--min-items`, `--small-cap`; `--max-institutions` for tests; `--float32`.

### Size budget: 9.5 GB

**Theme.** The default selection is Europeana's Art collection restricted to images: 1.26 million open-licence records with a media file from 799 institutions (about 1.9 GB, so the budget below caps nothing). "Art" is a thematic collection, not a media type; it is curated by Europeana and includes paintings, drawings and prints but also decorative objects, coins, maps and ethnographic items. Without the theme filter the same query matches 21 million images and the budget would cap 55 institutions at about 61,000 records each. `--theme` changes the collection; a folder harvested with one theme refuses another.

`metadata.csv` plus the embeddings are limited to 10 GB, with 9.5 GB as the target. A row costs about 1.5 KB (about 0.5 KB metadata, about 1 KB float16 vector, measured on a test sample), which is roughly 6.3 million images. All open image records in Europeana (21.0 million, `plan`, November 2026) would need about 31 GB.

`--budget-gb 9.5` spreads the budget with one rule: an institution contributes all of its records if it has fewer than a cap, and exactly `cap` otherwise, with the largest cap that fits. The old plan (10,000 each from the large institutions, everything from the small ones) is the special case of a fixed cap. The workflow:

```
python scripts/build_dataset.py plan    --budget-gb 9.5      # Art collection: 1.26 million images, nothing is capped
python scripts/build_dataset.py harvest --budget-gb 9.5      # about 13,000 requests, 30 minutes at 8 requests/s
(cluster) embed, one job per shard
python scripts/build_dataset.py merge   --max-gb 9.5         # trims to the real file sizes
```

`harvest` collects 10% more than the budget (`--margin`) and `merge --max-gb` trims to the real sizes, taking each institution's records in order of Europeana ID. It prints the final sizes and warns if they are over the limit.

Europeana publishes no daily quota for keys. Staff have mentioned about 120 requests per 10 seconds, the fair-use policy allows limits to change, and keys may not be shared. The harvest throttles itself and backs off on HTTP 429. For very large volumes Europeana offers dumps through FTP and OAI-PMH.

The embed stage makes about one thumbnail request per image (1.26 million for the Art selection), mostly to Europeana's thumbnail service and partly to institutions' IIIF servers. `--thumb-rate` (default 5 requests/s per job) throttles it, and the total is that rate times the number of jobs running at once (`--array=0-343%10` gives about 50 requests/s, so roughly 38 hours). No limit for the thumbnail service is published; start low and raise it if there are no errors. The throttle does not apply to institutions' own IIIF servers, which are spread over many hosts. The thumbnail service needs no key and its images are at most 400 px wide.

The notebook holds all vectors and metadata in memory (about 6 GB at the budget), which is fine on a workstation but is worth checking against the memory of the shared workspace.

## Dataset contract

```
data/DSI-Workshop/
  metadata.csv                       # one row per image, same order as the embeddings
  embeddings/clip_vit_b32.npz        # ids (N,), vectors (N, 512) float16, L2-normalised, model
  models/ViT-B-32.pt                 # CLIP weights
```

`metadata.csv` columns: `id` (Europeana ID), `institution`, `provider`, `country`, `type`, `title`, `creator`, `year`, `rights`, `landing_page` (`edmIsShownAt`), `full_image_url` (`edmIsShownBy`, the original file), `small_image_url` (the URL that served the image used for the embedding), `iiif_service` and `iiif_manifest` (filled only when the image service actually answered), `image_source` (`iiif` or `thumbnail`).

The `iiif_service` column is what allows the "look closely" step with a single URL request. IIIF services are detected from the media URL, so institutions whose service is not visible in the URL are served through thumbnails and have the original file as their only larger version.

## Instructor material (`instructor/`, git-ignored)

- `instructor/europeana_institutions_map.py`: the institution map, both Europeana's own embedded map (instructions in the docstring) and a self-made map from the Entity API with bubbles sized by record count. Removed from the notebooks to keep them short.
- `scripts/build_dataset.py` is not in that folder on purpose: it is pushed, so the embeddings can be calculated on other infrastructure.
