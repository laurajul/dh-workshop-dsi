# Digital Humanities Workshop: Computational Analysis of Cultural Heritage Images

![alt text](misc/assets/img/reals.webp)

*Images depicting **Shorelines** obtained from Europeana's aggregated collections via their public API. Europeana provides access to 50+ million digitized items from European museums, galleries, libraries and archives.*

---



## About This Workshop

This practical workshop introduces participants to computational approaches in the digital humanities through the analysis of European cultural heritage image collections. Drawing inspiration from the concept of "distant reading," the session explores how algorithms can be employed to "read" and interpret collections of visual and cultural data at scale.

Participants will work with **Europeana's API** and **IIIF (International Image Interoperability Framework)** to access standardized cultural heritage data from across Europe. You'll engage directly with dataset metadata and image embeddings generated via CLIP (Contrastive Language–Image Pretraining), employing these representations to categorize, cluster, and experiment with various forms of computational sorting and analysis.

The workshop combines conceptual discussion with hands-on exercises, providing an introduction to:
- How **APIs provide programmatic access** to cultural heritage collections
- How **IIIF standardizes** access to cultural heritage images across institutions
- How **machine learning models** operationalize notions of similarity, categorization, and meaning in visual data
- How to work with **cross-institutional datasets** spanning European collections

By reflecting on both the affordances and limitations of such algorithmic readings, the session aims to foster a critical understanding of how computational methods can augment and challenge traditional art-historical and cultural-analytical practices.

---

## Workshop Structure

The workshop consists of four Jupyter notebooks:

### Notebook 1: Working with Cultural Heritage APIs (`01_europeana_api_and_data.ipynb`)

Learn how to access and work with Europeana's aggregated cultural heritage data:

- **Understanding APIs**: What they are and why they matter for DH research
- **Exploring Collections**: Query countries and institutions in Europeana
- **Filtering Data**: Swedish institutions use case — how many are there?
- **Keyword Search**: Find paintings of rivers and discover who painted the most
- **OR Queries**: Search for multiple water bodies (river, sea, ocean, lake, seashore)
- **Universal Download Function**: Build a reusable function with customizable options
- **IIIF Introduction**: Learn about the International Image Interoperability Framework

**Key concepts**: RESTful APIs, JSON data formats, faceted search, OR queries, IIIF

---

### Notebook 2: Download Uppsala Collection & Semantic Search (`02_download_and_clip_search.ipynb`)

Download images and search them using natural language:

- **Download Collection**: Get images from Uppsala University via Europeana
- **Introduction to CLIP**: How neural networks connect images and text
- **Semantic Search**: Find images using natural language queries (e.g., "waterbody")
- **Prompt Engineering**: How different queries affect search results
- **Compare Queries**: See how "water", "river", and "ocean" find different images

**Key concepts**: Neural embeddings, semantic similarity, cosine similarity, prompt engineering

---

### Notebook 3: Find Similar Images (`03_find_similar_images.ipynb`)

Upload your own photo and find visually similar images in the collection:

- **Upload Photo**: Use ipywidgets to select an image from your laptop
- **Compute Embedding**: Generate a CLIP embedding for your photo
- **Find Matches**: Discover the most visually similar images in the Uppsala collection
- **Explore Similarity**: What does "visual similarity" mean to a neural network?

**Key concepts**: Image-to-image similarity, visual features, algorithmic interpretation

---

### Notebook 4: Advanced — Compute Your Own Embeddings (`04_advanced_compute_embeddings.ipynb`)

For when you have access to a GPU — compute embeddings for your own collections:

- **Configure Processing**: Choose CLIP model, batch size, and output location
- **Batch Processing**: Efficiently process hundreds or thousands of images
- **Save Embeddings**: Store embeddings in a reusable format
- **Verify Results**: Test that your embeddings work correctly

**Requirements**: NVIDIA GPU recommended (CPU works but is very slow)

**Key concepts**: Batch processing, model selection, GPU computing

---

## Prerequisites

### Technical Requirements

- **Python 3.8+** installed
- **Jupyter Notebook** or **JupyterLab**
- Basic familiarity with Python

### Hardware

- **Notebooks 1-3**: Any laptop (pre-calculated embeddings provided)
- **Notebook 4**: GPU recommended (for computing your own embeddings)

---

## Installation & Setup

### 1. Clone or Download This Repository

```bash
git clone https://github.com/yourusername/DH-Workshop.git
cd DH-Workshop
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

# For CLIP support (Notebooks 2-4):
pip install torch torchvision
pip install git+https://github.com/openai/CLIP.git
```

### 4. Get a Free Europeana API Key

1. Visit: https://pro.europeana.eu/page/get-api
2. Register for a free Europeana account
3. Request an API key from your account dashboard
4. Save your key to `notebooks/api-key-europeana.txt`

```bash
echo "your-api-key-here" > notebooks/api-key-europeana.txt
```

### 5. Start Jupyter

```bash
jupyter notebook
```

Navigate to the `notebooks/` directory and open `01_europeana_api_and_data.ipynb` to begin.

---

## Directory Structure

```
DH-Workshop/
├── notebooks/
│   ├── 01_europeana_api_and_data.ipynb      # API, search, download
│   ├── 02_download_and_clip_search.ipynb    # Uppsala + semantic search
│   ├── 03_find_similar_images.ipynb         # Upload photo, find similar
│   ├── 04_advanced_compute_embeddings.ipynb # GPU: compute embeddings
│   └── api-key-europeana.txt                # Your API key (gitignored)
├── scripts/
│   ├── precalculate_embeddings.py           # Instructor: pre-compute embeddings
│   └── download_images_batch.py             # Batch download utility
├── data/
│   └── europeana/
│       ├── uppsala_clip_embeddings.npz      # Pre-calculated embeddings
│       └── *.json                           # Search results
├── images/
│   ├── europeana/
│   │   └── Uppsala_University/              # Downloaded images
│   └── preview/
│       └── reals.webp                       # Workshop preview
├── misc/
│   └── README-europeana.md                  # API setup guide
├── requirements.txt                          # Python dependencies
└── README.md                                 # This file
```

---

## Workshop Data

### Uppsala University Collection

This workshop uses images from **Uppsala University** via Europeana:
- **~74,000 items** in the collection
- Historical photographs, artworks, manuscripts
- Open access under various Creative Commons licenses

### Pre-calculated Embeddings

For Notebooks 2-3, we provide pre-calculated CLIP embeddings:
- **File**: `data/europeana/uppsala_clip_embeddings.npz`
- **Model**: ViT-B/32
- This allows students to run semantic search without needing a GPU

---

## Datasets & Licenses

**Europeana Metadata**: Licensed under **CC0 1.0 Universal (Public Domain)**
- All metadata exposed through the Europeana API is freely reusable

**Individual Artworks**: Various licenses depending on source institution
- **CC0**: Public domain, no restrictions
- **CC BY**: Attribution required
- **CC BY-SA**: Attribution + share-alike required
- Always check the `rights` field in the API response

**CLIP Model**: Developed by OpenAI, available under the MIT License

**Attribution**: When using Europeana data, acknowledge both:
- Europeana (as the aggregator)
- The source institution (`dataProvider` field)

---

## For Instructors

### Pre-calculating Embeddings

Before the workshop, compute embeddings for the Uppsala collection:

```bash
# Download images first (using Notebook 01 or the download script)
python scripts/download_images_batch.py \
    --metadata data/europeana/uppsala_search_results.json \
    --output images/europeana/Uppsala_University \
    --max 5000

# Compute embeddings
python scripts/precalculate_embeddings.py \
    --images_dir images/europeana/Uppsala_University \
    --output data/europeana/uppsala_clip_embeddings.npz \
    --model ViT-B/32
```

The embeddings file (~20MB for 5000 images) should be distributed to students.

---

## Further Resources

### Europeana & IIIF

- **[Europeana Portal](https://www.europeana.eu/)** - Browse 50+ million items
- **[Europeana API Documentation](https://pro.europeana.eu/page/apis)** - Technical documentation
- **[Get Europeana API Key](https://pro.europeana.eu/page/get-api)** - Free registration
- **[IIIF Consortium](https://iiif.io/)** - IIIF specifications and community
- **[IIIF Awesome List](https://github.com/IIIF/awesome-iiif)** - Tools and resources

### Other Cultural Heritage APIs

- [Rijksmuseum API](https://data.rijksmuseum.nl/) - Dutch national collection with IIIF
- [Metropolitan Museum API](https://metmuseum.github.io/) - American art collection
- [Harvard Art Museums API](https://harvardartmuseums.org/collections/api) - With IIIF support

### Digital Humanities & Machine Learning

- **[CLIP by OpenAI](https://openai.com/research/clip)** - Original paper and implementation
- **[Programming Historian](https://programminghistorian.org/)** - DH tutorials
- **[Distant Viewing Toolkit](https://distantviewing.org/)** - Computer vision for DH

---
