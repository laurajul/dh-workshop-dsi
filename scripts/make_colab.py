"""Make the Google Colab versions of the workshop notebooks.

    python scripts/make_colab.py

Reads notebooks/01_iiif, 02_europeana, 03_clip_search and 0Z_final_task and writes colab/<same name>.ipynb.
The content is the same; a few cells are added at the top: clone the repository (so every path is the same as on the
workshop server), and, for notebook 03, mount Google Drive and link the shared data folder to ~/data.
Run it again whenever the notebooks change.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = ["01_iiif", "02_europeana", "03_clip_search", "0Z_final_task"]
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
    md("colab-md", "**Google Colab version.** Run the cell below first. It gets the workshop code, so that every path is the same as on the workshop server. Otherwise this notebook is the same."),
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

SHARED_FOLDER_URL = "PASTE-THE-LINK-TO-THE-SHARED-GOOGLE-DRIVE-FOLDER-HERE"     # <-- the instructor puts the link here
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


def build(name):
    nb = json.loads((ROOT / "notebooks" / f"{name}.ipynb").read_text(encoding="utf-8"))
    cells = nb["cells"]
    extra = list(CLONE)
    if name == "03_clip_search":
        extra += CLIP_SETUP
    if name == "0Z_final_task":
        replace_in(cells, "f-kept", "in the file browser on the left open `my_images/`, right-click the file, **Download**.",
                   "in the file browser on the left (folder icon) open `DH-Workshop/notebooks/my_images/`, right-click the file, **Download**. Or run the cell after the list: it downloads all kept pictures as one zip.")
        k = [c["id"] for c in cells].index("f-kept-code")
        cells.insert(k + 1, ZIP_CELL)
    nb["cells"] = cells[:1] + extra + cells[1:]            # the banner stays first
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                      "language_info": {"name": "python"}, "colab": {"provenance": []}}
    out = ROOT / "colab" / f"{name}.ipynb"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out.relative_to(ROOT), f"({len(nb['cells'])} cells)")


if __name__ == "__main__":
    for n in NAMES:
        build(n)
