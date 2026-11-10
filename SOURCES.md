# Sources

Everything this workshop draws on. The first sections are the material the workshop was built from; the later ones are the sites and services the notebooks use.

## Reference material (`misc/reference/`)

- Raemy, J. A. (2026). *IIIF in Switzerland: A Landscape of Compatible Platforms and Engaged Institutions* (Version 1.0). Report, University of Bern. https://doi.org/10.5281/zenodo.23242984 (CC BY 4.0). File: `raemy_iiif-switzerland_1.0.pdf`. Basis of the Swiss platform overview in notebook 1.
- Loosli, U. (2025). *International Image Interoperability Framework (IIIF): Der Standard für digitales Bildmaterial*. AGIK workshop, 2 September 2025, University of Bern. Slides, `WS20250902_IIIF.pdf`.
- Basir, S. (2025). *Exploring Neural IR Approaches in Europeana: Unlocking Multilingual Insights for Cultural Heritage Search*. MSc thesis, Delft University of Technology. `msc2025basir.pdf`.
- `links.txt`: the ZB viewers listed there, https://beta.viewer.zb.uzh.ch/ and https://viewer.zb.uzh.ch/detektiiif_en.html (detektIIIF).
- `paper_style.mplstyle`: a matplotlib style file (not a source, kept with the references).

## Video and tutorials

- Zentralbibliothek Zürich, *Was ist IIIF?* (video). https://www.youtube.com/watch?v=nfV68YoaQlI
- ZB-Lab, Zentralbibliothek Zürich (IIIF introduction video tutorials; the idea of starting from the browser's Network tab comes from these). https://www.zb.uzh.ch/en/ueber-uns/zb-lab

## The Battle of Murten (notebook 1, opening example)

- Terapixel panorama of the Battle of Murten (EPFL). https://terapixelpanorama.ch/
- The panorama's IIIF image server, as seen in the browser's Network tab. https://murtenpanorama.epfl.ch/iiif/part123_decurve_align_crop_20240620_75_512.tif/1006421
- Detail of the panorama painting of the Battle of Murten by Louis Braun, shown at Expo.02. Photo: Riccardo Speziari, Wikimedia Commons (CC BY-SA 3.0). https://de.wikipedia.org/wiki/Datei:Expo_02_-_Ausschnitt_Panoramagem%C3%A4lde_Schlacht_bei_Murten_-_Louis_Braun.jpg

## IIIF

- IIIF, the consortium. https://iiif.io/
- Image API 3.0. https://iiif.io/api/image/3.0/
- Presentation API 3.0. https://iiif.io/api/presentation/3.0/
- Presentation 3 JSON-LD context. http://iiif.io/api/presentation/3/context.json
- IIIF Cookbook, and the book recipe used as an example. https://iiif.io/api/cookbook/ and https://iiif.io/api/cookbook/recipe/0009-book-1/
- IIIF tools overview. https://iiif.io/get-started/tools/
- Finding resources (IIIF guides). https://guides.iiif.io/finding_resources/
- IIIF logo, Wikimedia Commons. https://commons.wikimedia.org/wiki/File:International_Image_Interoperability_Framework_logo.png
- Mirador (viewer, v3.4.3 loaded from jsDelivr; demo). https://projectmirador.org/ and https://projectmirador.org/demo/
- Universal Viewer. https://universalviewer.io/
- Tropy. https://tropy.org/
- Biblissima portal. https://portail.biblissima.fr/

## Swiss platforms and IIIF examples (notebook 1)

- e-rara (the Krüdener manuscript example). https://www.e-rara.ch/ and https://www.e-rara.ch/bes_1/content/pagetext/32643449
- e-codices (Cod. Sang. 1). https://www.e-codices.ch/, https://www.e-codices.unifr.ch/en/csg/0001/ and https://www.e-codices.unifr.ch/metadata/iiif/csg-0001/manifest.json
- e-manuscripta. https://www.e-manuscripta.ch/ and https://www.e-manuscripta.ch/snl/content/pagetext/4317519
- Fragmentarium. https://fragmentarium.ms/ and https://fragmentarium.ms/metadata/iiif/F-mp8l/manifest.json
- Gallica (BnF). https://gallica.bnf.fr/
- Art Institute of Chicago API, manifest example. https://api.artic.edu/api/v1/artworks/143948/manifest.json
- Juliane von Krüdener (background to the e-rara example). https://de.wikipedia.org/wiki/Juliane_von_Kr%C3%BCdener

## Europeana (notebooks 1 to 3)

- Europeana. https://www.europeana.eu/
- Europeana APIs overview. https://pro.europeana.eu/page/apis
- Get an API key. https://pro.europeana.eu/page/get-api
- Search API documentation. https://pro.europeana.eu/page/search
- Record API (`api.europeana.eu/record/v2`). https://pro.europeana.eu/page/apis
- Europeana Data Model (EDM) documentation. https://pro.europeana.eu/page/edm-documentation
- Europeana IIIF Presentation endpoint. https://iiif.europeana.eu/presentation/
- Items used as examples: Rijksmuseum drawing https://www.europeana.eu/en/item/90402/RP_T_1904_190 (manifest https://iiif.europeana.eu/presentation/90402/RP_T_1904_190/manifest), and the Salzburg Museum banknote (Waizenkirchen, 20 Heller) https://www.europeana.eu/en/item/1387/https___id_kulturpool_at_013cf817_e57a_4289_96b3_2a068c7fe756_cho

## CLIP (notebook 3)

- OpenAI, CLIP: Connecting text and images. https://openai.com/research/clip (also https://openai.com/index/clip/). Model used: ViT-B/32. Code: https://github.com/openai/CLIP

## Workshop infrastructure

- Workshop repository. https://github.com/laurajul/dh-workshop-dsi
- Hand-in folder (Switch drive). https://drive.switch.ch/index.php/s/JeirWKGtP2HBxEm
