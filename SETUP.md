# Setup

## On the workshop server (JupyterHub)

1. Open a **Terminal** in JupyterLab.
2. Copy the script from the shared folder to your home, and run it:
   ```bash
   cp /srv/shared/DSI-Workshop/setup.sh ~
   chmod +x ~/setup.sh
   ~/setup.sh
   ```
3. Open `DH-Workshop/notebooks/01_iiif.ipynb` and choose the kernel **dh-workshop**.

The script clones this repository to `~/DH-Workshop`, links the shared data folder to `~/data` (if nothing is there yet), and registers the `dh-workshop` kernel, which uses the packages already installed in the shared folder. It is safe to run again.

If it stops with an error, send the message to the workshop team.

## On your own computer

Linux, Python 3.12:

```bash
git clone https://github.com/laurajul/dh-workshop-dsi.git
cd dh-workshop-dsi
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name dh-workshop
```

The dataset is not in the repository. Get the `DSI-Workshop` folder (with `metadata.csv`, `embeddings/` and `models/`) from the instructor and put it in `data/DSI-Workshop/`, or point to it with the environment variable `DSI_WORKSHOP_DIR`. The notebooks look for it in `DSI_WORKSHOP_DIR`, `~/shared/DSI-Workshop`, `~/data`, then `data/DSI-Workshop`.

## Handing in

Files for the final task go in a folder with your name on the workshop's Switch drive. The link is in `0Z_final_task.ipynb`.
