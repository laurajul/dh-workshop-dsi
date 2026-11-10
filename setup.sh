#!/usr/bin/env bash
# DH-Workshop setup – run once at the beginning of the workshop.
#
# Copy this file to your home directory first, then:
#   chmod +x setup.sh && ./setup.sh
#
#   1. clones the workshop repository into ~/DH-Workshop
#   2. links the shared data folder to ~/data (only if not already present)
#   3. registers a Jupyter kernel "dh-workshop" that uses the system Python 3.12
#      together with the prebuilt packages in the shared folder
#      (nothing is installed per user)
set -euo pipefail

REPO_URL="https://github.com/laurajul/dh-workshop-dsi.git"
REPO_DIR="$HOME/DH-Workshop"
SHARED_DIR="/srv/shared/DSI-Workshop"
ENV_DIR="$SHARED_DIR/.venv"          # prebuilt environment (uploaded via azcopy)
# azcopy drops the venv's python symlinks, so we use the system Python 3.12
# (same version the venv was built with) and point it at the venv's packages.
PYTHON_BIN="/usr/bin/python3.12"
SITE_PACKAGES="$ENV_DIR/lib/python3.12/site-packages"
DATA_LINK="$HOME/data"
KERNEL_NAME="dh-workshop"

# --- checks -----------------------------------------------------------------
if [ ! -d "$SHARED_DIR" ]; then
    echo "ERROR: $SHARED_DIR does not exist. Please ask the workshop team for help." >&2
    exit 1
fi
if [ ! -x "$PYTHON_BIN" ]; then
    echo "ERROR: $PYTHON_BIN not found. Please ask the workshop team." >&2
    exit 1
fi
if [ ! -d "$SITE_PACKAGES" ]; then
    echo "ERROR: $SITE_PACKAGES not found. The shared environment is missing." >&2
    exit 1
fi
if ! PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_PACKAGES" "$PYTHON_BIN" -c "import ipykernel" >/dev/null 2>&1; then
    echo "ERROR: the shared environment cannot be loaded (ipykernel import failed)." >&2
    exit 1
fi

# --- 1. clone repository into home ------------------------------------------
if [ -d "$REPO_DIR/.git" ]; then
    echo ">>> Repository already exists at $REPO_DIR, skipping clone."
else
    echo ">>> Cloning $REPO_URL into $REPO_DIR ..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# --- 2. link shared data folder to ~/data -----------------------------------
# Never overwrite or nest anything: only create the link if nothing is at ~/data.
if [ -L "$DATA_LINK" ]; then
    echo ">>> $DATA_LINK is already a symlink (-> $(readlink "$DATA_LINK")), leaving it as is."
elif [ -e "$DATA_LINK" ]; then
    echo ">>> WARNING: $DATA_LINK already exists and is not a symlink, leaving it untouched." >&2
else
    echo ">>> Linking $SHARED_DIR -> $DATA_LINK ..."
    ln -s "$SHARED_DIR" "$DATA_LINK"
fi

# --- 3. Jupyter kernel from the shared environment --------------------------
# Writes ~/.local/share/jupyter/kernels/dh-workshop/kernel.json and adds an
# "env" block so the kernel finds the shared packages. Re-running refreshes it.
echo ">>> Registering Jupyter kernel '$KERNEL_NAME' ..."
PYTHONNOUSERSITE=1 PYTHONPATH="$SITE_PACKAGES" "$PYTHON_BIN" -m ipykernel install \
    --user --name="$KERNEL_NAME" --display-name "$KERNEL_NAME"

KERNEL_JSON="$HOME/.local/share/jupyter/kernels/$KERNEL_NAME/kernel.json"
"$PYTHON_BIN" - "$KERNEL_JSON" "$SITE_PACKAGES" <<'PY'
import json, sys
path, site = sys.argv[1:3]
with open(path) as f:
    spec = json.load(f)
spec["env"] = {"PYTHONPATH": site, "PYTHONNOUSERSITE": "1"}
with open(path, "w") as f:
    json.dump(spec, f, indent=1)
PY

echo
echo "Setup complete. Start your notebooks with the '$KERNEL_NAME' kernel."
