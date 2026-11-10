"""Keep pictures for the presentation (notebook 05).

Result cards, pictures with regions and your own uploads end up in one folder, `my_images/` next to the notebooks.
The presentation builder of notebook 05 lets you pick from that folder. Nothing here needs to be called by hand:
the "Keep for my presentation" button under a result does it.
"""
import json
from pathlib import Path

import ipywidgets as widgets
from IPython.display import display
from PIL import Image, ImageDraw

MY_IMAGES = Path(__file__).resolve().parent / "my_images"
_CAPTIONS = "captions.json"


def captions():
    f = MY_IMAGES / _CAPTIONS
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def set_caption(filename, text):
    MY_IMAGES.mkdir(exist_ok=True)
    c = captions()
    c[filename] = text
    (MY_IMAGES / _CAPTIONS).write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def library():
    """The kept pictures, newest first: a list of (file name, caption)."""
    if not MY_IMAGES.exists():
        return []
    files = sorted(MY_IMAGES.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    c = captions()
    return [(p.name, c.get(p.name, "")) for p in files]


def keep(image, caption=""):
    """Save a PIL image into my_images/ (as JPEG) and return its file name."""
    MY_IMAGES.mkdir(exist_ok=True)
    n = len(list(MY_IMAGES.glob("*.jpg"))) + 1
    while (MY_IMAGES / f"kept-{n:03d}.jpg").exists():
        n += 1
    name = f"kept-{n:03d}.jpg"
    im = image.convert("RGB")
    im.thumbnail((1600, 1600))
    im.save(MY_IMAGES / name, "JPEG", quality=88)
    set_caption(name, caption)
    return name


def keep_button(make_image, caption=""):
    """Show a button that keeps the picture returned by make_image() (called only on click)."""
    btn = widgets.Button(description="Keep for my presentation", icon="star", layout=widgets.Layout(width="230px"))
    out = widgets.Label("")

    def click(_):
        try:
            keep(make_image(), caption)
            btn.description, btn.disabled = "Kept", True
            out.value = "Saved in my_images/. Pick it in the presentation builder (notebook 05)."
        except Exception as e:      # never break the notebook because of a button
            out.value = f"Could not keep it ({type(e).__name__})."

    btn.on_click(click)
    display(widgets.HBox([btn, out]))


def contact_sheet(rows, thumb=150, pad=8, label_h=18):
    """One picture from rows = [(label, [PIL images]), ...]: a labelled row of square thumbnails per entry."""
    cols = max(len(imgs) for _, imgs in rows)
    w = cols * (thumb + pad) + pad
    h = len(rows) * (thumb + label_h + pad) + pad
    sheet = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(sheet)
    for r, (label, imgs) in enumerate(rows):
        y = pad + r * (thumb + label_h + pad)
        d.text((pad, y), str(label)[:90], fill=(31, 36, 48))
        for c, im in enumerate(imgs):
            im = im.convert("RGB")
            s = min(im.size)
            im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2)).resize((thumb, thumb))
            sheet.paste(im, (pad + c * (thumb + pad), y + label_h))
    return sheet
