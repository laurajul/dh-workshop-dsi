# Computational Approaches to Cultural Heritage Image Collections

![Images of shorelines from Europeana](misc/assets/img/reals.webp)

A two-hour digital humanities workshop on finding, reading and searching digitised cultural heritage **programmatically**: IIIF, the Europeana API, and searching images by what they look like with CLIP.

## Overview

1. **The IIIF standards:** how any viewer can show images from any institution, at any size and detail.
2. **The Europeana corpus:** what is inside Europeana's aggregated collections, and how to query it with the API.
3. **Semantic search:** searching images by what they look like with CLIP, with words, with an image, and with a region of an image.
4. **A small task, then short presentations:** each participant shows what they found, then we conclude.

## Notebooks

Run them in order, in `notebooks/`, with the `dh-workshop` kernel.

**Without the workshop server:** the whole workshop in one Google Colab notebook (all four parts, set up once at the top, see [SETUP.md](SETUP.md)):

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/laurajul/dh-workshop-dsi/blob/main/colab/workshop.ipynb)

| Notebook | About |
|---|---|
| `01_iiif.ipynb` | IIIF in practice: manifests, image URLs, regions, annotations, viewers |
| `02_europeana.ipynb` | Europeana: aggregation, the search API, metadata, finding IIIF manifests |
| `03_clip_search.ipynb` | Keyword search against search by embedding, searching with an image, whole image against region |
| `04_final_task.ipynb` | The final task: what to show and how to hand it in |

The helper code is in `notebooks/*.py`. The dataset (about 600,000 open Europeana art images as metadata and CLIP vectors, no images) is **not** in this repository; see [SETUP.md](SETUP.md).

## Other folders

- `colab/`: the whole workshop as one Google Colab notebook (made by `scripts/make_colab.py`)
- `scripts/`: how the dataset was built (harvest, images, embeddings), for instructors
- `instructor/`: tools for the instructor
- `misc/`: images used in the notebooks, reference material
- `ARCHIVE/`: earlier and longer versions, kept for a later seminar (not tracked by git)

Sources of all material used: [SOURCES.md](SOURCES.md).
