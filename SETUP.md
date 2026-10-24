# Workshop Setup Guide

## System Requirements

| | Minimum | Recommended |
|---|---|---|
| **RAM** | 4 GB | 8 GB |
| **Disk space** | 4 GB free | 6 GB free |
| **Internet** | Required during setup | — |

**Supported operating systems:**
- Windows 10 or 11
- macOS 11 (Big Sur) or later
- Ubuntu 20.04 or later

---

## What Gets Installed

The setup script will automatically install:

- **uv** — fast Python package manager (installed to your user folder, no admin rights needed)
- **Python 3.11** — managed by uv, isolated from any other Python on your system
- **Python packages** — torch, CLIP, numpy, Pillow, JupyterLab, and others (see `requirements.txt`)
- **DH Workshop kernel** — a Jupyter kernel that appears as *"DH Workshop"* in JupyterLab

The **CLIP model** (ViT-B/32, ~350 MB) is downloaded automatically the first time you run a notebook that loads it.

---

## Data Files

The instructor will provide two folders to place inside the project's `data/` directory:

```
DH-Workshop/
└── data/
    ├── images/
    │   └── <Collection Name>/       ← ~1 000 thumbnail images
    └── embeddings/
        └── <Collection Name>/       ← pre-calculated CLIP embeddings (.npz)
```

These are **not** part of the git repository and must be copied in separately.

---

## Installation Instructions

### macOS

1. Open **Terminal** (search for it in Spotlight with ⌘ Space)
2. Run:
   ```bash
   bash <(curl -s https://raw.githubusercontent.com/laurajul/DH-Workshop/main/install_mac.sh)
   ```
   Or download `install_mac.sh`, then run:
   ```bash
   bash ~/Downloads/install_mac.sh
   ```

---

### Linux

1. Open a terminal
2. Run:
   ```bash
   bash <(curl -s https://raw.githubusercontent.com/laurajul/DH-Workshop/main/install_linux.sh)
   ```
   Or download `install_linux.sh`, then run:
   ```bash
   bash ~/Downloads/install_linux.sh
   ```

---

### Windows

1. Download `install_windows.bat` from the repository
2. Double-click it

> **Note for Windows users:** Git must be installed before running the script.
> Download it from [https://git-scm.com/download/win](https://git-scm.com/download/win) and install with default settings, then run the `.bat` file.

---

## After Installation

JupyterLab will open automatically in your browser. When you open a notebook:

1. Click the **kernel selector** in the top-right corner (it may say "No Kernel" or "Python 3")
2. Select **"DH Workshop"** from the list
3. The instructor will walk you through this step at the start of the session

---

## Troubleshooting

**"uv: command not found" after install**
Close and reopen your terminal, then try again.

**The CLIP model download is slow**
The model (~350 MB) downloads once and is then cached. This happens the first time a notebook loads CLIP.

**Package installation fails**
Make sure you have a stable internet connection. Try running the install script again — it will skip steps already completed.

**JupyterLab doesn't open**
After the script finishes, you can start it manually:
```bash
cd ~/DH-Workshop
.venv/bin/jupyter lab          # macOS / Linux
.venv\Scripts\jupyter lab      # Windows
```
