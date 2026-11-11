"""Make the Google Colab version of the workshop: ONE notebook with all parts.

    python scripts/make_colab.py

Reads notebooks/01_iiif, 02_europeana, 03_clip_search and 04_final_task and writes colab/workshop.ipynb.
The content is the same, in that order. A setup section is added once at the top: clone the repository (so every path
is the same as on the workshop server), install CLIP, mount Google Drive and link the shared data folder to ~/data.
Run it again whenever the notebooks change.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ["01_iiif", "02_europeana", "03_clip_search", "04_final_task"]
REPO = "https://github.com/laurajul/dh-workshop-dsi.git"


def md(cid, text):
    lines = text.split("\n")
    return {"cell_type": "markdown", "id": cid, "metadata": {}, "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]}


def code(cid, text):
    lines = text.split("\n")
    return {"cell_type": "code", "id": cid, "metadata": {}, "execution_count": None, "outputs": [],
            "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]}


def text_of(cell):
    return "".join(cell["source"])


def replace_in(cells, cid, old, new):
    cell = next(c for c in cells if c["id"] == cid)
    t = text_of(cell)
    assert old in t, (cid, old)
    lines = t.replace(old, new).split("\n")
    cell["source"] = [l + "\n" for l in lines[:-1]] + [lines[-1]]


CLONE = [
    md("colab-md", "**Google Colab version: the whole workshop in one notebook.** Run the setup cells below once, from top to bottom (about two minutes). They get the workshop code, so that every path is the same as on the workshop server, and connect your Google Drive for the data of part 3. Then go on with the parts in order. If Colab restarts the runtime, run the setup cells again."),
    code("colab-clone", f'''# Colab setup: run this cell first.
import os
import subprocess
import sys

if not os.path.exists("/content/DH-Workshop"):
    subprocess.run(["git", "clone", "-q", "{REPO}", "/content/DH-Workshop"], check=True)
os.chdir("/content/DH-Workshop/notebooks")
sys.path.insert(0, os.getcwd())
print("ready in", os.getcwd())'''),
]

CLIP_SETUP = [
    code("colab-pip", "%pip install -q ftfy regex git+https://github.com/openai/CLIP.git"),
    md("colab-drive-md", '''## The shared data folder (Google Drive)

The collection (metadata and CLIP vectors) is in a shared Google Drive folder.

1. Run the first cell below and allow access to your Drive.
2. Open the folder with the link that the second cell shows. At the top, click the folder name, then **Organise, Add shortcut, My Drive**.
3. Run the second cell. It links the folder to `~/data`, the same path as on the workshop server.'''),
    code("colab-drive", 'from google.colab import drive\n\ndrive.mount("/content/drive")'),
    code("colab-link", '''import os
import ipywidgets as widgets

SHARED_FOLDER_URL = "https://drive.google.com/drive/folders/1BKpsYAdGA07dQbtECEaYIhw5oOB0oChH?usp=sharing"     # <-- the instructor puts the link here
FOLDER_NAME = "DSI-Workshop"        # the name of the folder in your My Drive after adding the shortcut

display(widgets.HTML(f"<a href='{SHARED_FOLDER_URL}' target='_blank' style='font:16px sans-serif'>{SHARED_FOLDER_URL}</a>"))

src = f"/content/drive/MyDrive/{FOLDER_NAME}"
link = os.path.expanduser("~/data")
if os.path.islink(link) or os.path.exists(link):
    print(link, "is already there, leaving it as it is.")
elif not os.path.exists(os.path.join(src, "metadata.csv")):
    print("metadata.csv not found in", src, "- add the shortcut to My Drive (step 2) and check FOLDER_NAME.")
else:
    os.symlink(src, link)
    print("linked", src, "->", link)'''),
]

ZIP_CELL = code("colab-zip", '''import shutil
from google.colab import files
from keep_helpers import MY_IMAGES

if MY_IMAGES.exists() and any(MY_IMAGES.glob("*.jpg")):
    files.download(shutil.make_archive("/content/my_images", "zip", MY_IMAGES))      # one zip with all kept pictures
else:
    print("No kept pictures yet.")''')


def load_part(n, name):
    nb = json.loads((ROOT / "notebooks" / f"{name}.ipynb").read_text(encoding="utf-8"))
    cells = nb["cells"]
    if name == "04_final_task":
        replace_in(cells, "f-kept", "in the file browser on the left open `my_images/`, right-click the file, **Download**.",
                   "in the file browser on the left (folder icon) open `DH-Workshop/notebooks/my_images/`, right-click the file, **Download**. Or run the cell after the list: it downloads all kept pictures as one zip.")
        k = [c["id"] for c in cells].index("f-kept-code")
        cells.insert(k + 1, ZIP_CELL)
    for c in cells:                                         # cell ids must stay unique across the parts
        c["id"] = f"p{n}-{c['id']}"
    return cells


def build():
    parts = [load_part(n, name) for n, name in enumerate(PARTS, 1)]
    setup = CLONE + CLIP_SETUP
    cells = parts[0][:1] + setup + parts[0][1:]            # the welcome banner stays first
    for p in parts[1:]:
        cells += p
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "colab": {"provenance": []}}}
    ids = [c["id"] for c in cells]
    assert len(ids) == len(set(ids))
    out = ROOT / "colab" / "workshop.ipynb"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out.relative_to(ROOT), f"({len(cells)} cells)")


if __name__ == "__main__":
    build()
