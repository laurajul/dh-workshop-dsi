"""A presentation builder for notebook 05: fill in boxes, tick pictures, publish one HTML file.

    builder = PresentationBuilder()
    builder.show()           # the form
    builder.publish()        # writes shared/Presentation/<name>.html

Pictures come from `my_images/` (the "Keep for my presentation" buttons of notebooks 03 and 04, and your uploads).
What you type is saved as you go (my_images/builder_state.json), so a restarted kernel loses nothing.
"""
import html
import json
from io import BytesIO
from pathlib import Path

import ipywidgets as widgets
from IPython.display import clear_output, display
from PIL import Image

from clip_helpers import PROJECT_ROOT
from keep_helpers import MY_IMAGES, keep, library, set_caption
from region_helpers import Deck, img_tag, show_html, slug

SLIDES = [
    ("Question and data", "What did you want to find out, and which data did you use?"),
    ("What I did", "The steps, in a few words."),
    ("Result 1", "What did you find? One clear picture is better than five busy ones."),
    ("Result 2", "A second result, or a comparison with the first."),
    ("A limitation", "Where does it fail, or what can it not tell you? One concrete example."),
    ("Anything else", "Optional. Leave empty to skip."),
]
STATE = MY_IMAGES / "builder_state.json"


def presentation_dir():
    # ~/shared/Presentation/ on the workshop server, otherwise data/Presentation/ in the project.
    base = Path.home() / "shared"
    base = base / "Presentation" if base.exists() else PROJECT_ROOT / "data" / "Presentation"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _thumb_bytes(name, size=240):
    im = Image.open(MY_IMAGES / name).convert("RGB")
    im.thumbnail((size, size))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


class PresentationBuilder:
    def __init__(self):
        saved = {}
        try:
            saved = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        except Exception:
            pass
        S = widgets.Layout(width="95%")
        self.name = widgets.Text(saved.get("name", ""), description="Your name", placeholder="e.g. Anna Meier", layout=S, style={"description_width": "90px"})
        self.title = widgets.Text(saved.get("title", ""), description="Title", placeholder="a short title for your talk", layout=S, style={"description_width": "90px"})
        self.question = widgets.Textarea(saved.get("question", ""), description="Question", placeholder="one sentence: what did you want to find out?",
                                         layout=widgets.Layout(width="95%", height="60px"), style={"description_width": "90px"})
        self.headings, self.notes, self.sel, self.galleries, self.panels = [], [], [], [], []
        for n, (head, hint) in enumerate(SLIDES):
            s = saved.get("slides", [{}] * len(SLIDES))[n] if n < len(saved.get("slides", [])) else {}
            self.headings.append(widgets.Text(s.get("heading", head), description="Heading", layout=S, style={"description_width": "90px"}))
            self.notes.append(widgets.Textarea(s.get("notes", ""), description="Text", placeholder=hint + "  (one point per line)",
                                               layout=widgets.Layout(width="95%", height="90px"), style={"description_width": "90px"}))
            self.sel.append([f for f in s.get("images", []) if (MY_IMAGES / f).exists()])
            self.galleries.append(widgets.VBox())
        for n in range(len(SLIDES)):
            up = widgets.FileUpload(accept="image/*", multiple=True, description="Upload pictures", icon="upload", layout=widgets.Layout(width="190px"))
            up.observe(lambda ch, n=n, up=up: self._uploaded(n, up), names="value")
            refresh = widgets.Button(description="Refresh", icon="refresh", layout=widgets.Layout(width="110px"))
            refresh.on_click(lambda _: self._refresh())
            hint = widgets.HTML("<div style='font:13px sans-serif;color:#555;margin:6px 0'>Tick the pictures to show, in the order you want them. "
                                "Screenshots: save them as a file, then upload them here. A picture you upload stays in the list for all slides.</div>")
            self.panels.append(widgets.VBox([self.headings[n], self.notes[n], hint, widgets.HBox([up, refresh]), self.galleries[n]]))
        self.tabs = widgets.Tab(children=self.panels, titles=[f"{i + 1}. {h}" for i, (h, _) in enumerate(SLIDES)])
        self.preview_out = widgets.Output()
        preview = widgets.Button(description="Preview", icon="eye", button_style="info", layout=widgets.Layout(width="130px"))
        preview.on_click(lambda _: self._preview())
        self.msg = widgets.HTML("")
        head = widgets.VBox([widgets.HTML("<h3 style='margin:0'>Your presentation</h3>"), self.name, self.title, self.question])
        self.ui = widgets.VBox([head, self.tabs, widgets.HBox([preview, self.msg]), self.preview_out])
        for w in [self.name, self.title, self.question, *self.headings, *self.notes]:
            w.observe(lambda ch: self._save(), names="value")
        self._refresh()

    # ---- pictures

    def _refresh(self):
        lib = library()
        for n, box in enumerate(self.galleries):
            tiles = []
            for fn, cap in lib:
                img = widgets.Image(value=_thumb_bytes(fn), format="jpeg", width=150)
                tick = widgets.Checkbox(fn in self.sel[n], description="show", indent=False, layout=widgets.Layout(width="150px"))
                tick.observe(lambda ch, n=n, fn=fn: self._tick(n, fn, ch["new"]), names="value")
                caption = widgets.Text(cap, placeholder="caption", layout=widgets.Layout(width="150px"))
                caption.observe(lambda ch, fn=fn: set_caption(fn, ch["new"]), names="value")
                tiles.append(widgets.VBox([img, tick, caption], layout=widgets.Layout(margin="4px 10px 4px 0")))
            box.children = [widgets.Box(tiles, layout=widgets.Layout(flex_flow="row wrap")) if tiles else
                            widgets.HTML("<i>No pictures yet. Use the <b>Keep for my presentation</b> button under a result in notebook 03 or 04, or upload a file.</i>")]

    def _tick(self, n, fn, on):
        if on and fn not in self.sel[n]:
            self.sel[n].append(fn)
        if not on and fn in self.sel[n]:
            self.sel[n].remove(fn)
        self._save()

    def _uploaded(self, n, up):
        if not up.value:
            return
        for f in up.value:                                   # ipywidgets 8: a tuple of dicts; ipywidgets 7: a dict of dicts
            item = f if isinstance(f, dict) else up.value[f]
            try:
                name = keep(Image.open(BytesIO(bytes(item["content"]))), Path(item["name"]).stem)
                self.sel[n].append(name)
            except Exception:
                self.msg.value = f"<span style='color:#b00'>Could not read {html.escape(str(item.get('name')))} as a picture.</span>"
        up.value = ()
        self._refresh()
        self._save()

    # ---- state, deck, publish

    def _save(self):
        try:
            MY_IMAGES.mkdir(exist_ok=True)
            STATE.write_text(json.dumps(dict(name=self.name.value, title=self.title.value, question=self.question.value,
                                             slides=[dict(heading=self.headings[i].value, notes=self.notes[i].value, images=self.sel[i])
                                                     for i in range(len(SLIDES))]), ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def deck(self):
        title = self.title.value.strip() or "My presentation"
        deck = Deck(title, author=self.name.value.strip(), subtitle=self.question.value.strip())
        caps = {fn: c for fn, c in library()}
        for i in range(len(SLIDES)):
            lines = [ln.strip() for ln in self.notes[i].value.splitlines() if ln.strip()]
            text = "\n".join(ln if ln.startswith("- ") else "- " + ln for ln in lines)
            imgs = [fn for fn in self.sel[i] if (MY_IMAGES / fn).exists()]
            if not text and not imgs:
                continue                                    # empty slides are left out
            heading = self.headings[i].value.strip() or SLIDES[i][0]
            figs = "".join(f"<figure style='margin:0 16px 10px 0'>{img_tag(Image.open(MY_IMAGES / fn), 1000, 'max-height:58vh;max-width:' + ('92vw' if len(imgs) == 1 else '44vw'))}"
                           f"<figcaption class='sub' style='font-size:14px'>{html.escape(caps.get(fn, ''))}</figcaption></figure>" for fn in imgs)
            deck.slides.append(f"<h2>{html.escape(heading)}</h2>" + (f"<div class='row'>{figs}</div>" if figs else "") + Deck._text(text))
        return deck

    def show(self):
        display(self.ui)

    def _preview(self):
        with self.preview_out:
            clear_output()
            show_html(self.deck().html(), 560)

    def publish(self):
        """Write the presentation to shared/Presentation/<name>.html."""
        if not self.name.value.strip():
            raise ValueError("Please enter your name in the form above first.")
        self._save()
        path = presentation_dir() / f"{slug(self.name.value)}.html"
        self.deck().save(path)
        print(f"Saved: {path}\nOpen it in a browser to present. Arrow keys or the buttons move between slides.\nRun this cell again after changes: it replaces the file.")
        return path
