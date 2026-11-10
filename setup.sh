#!/usr/bin/env bash
# DH-Workshop setup – run once at the beginning of the workshop.
#
# Copy this file to your home directory first, then:
#   chmod +x setup.sh && ./setup.sh
#
#   1. clones the workshop repository into ~/DH-Workshop
#   2. links the shared data folder to ~/data (only if not already present)
#   3. registers a Jupyter kernel "dh-workshop" that uses the prebuilt
#      environment in the shared folder (nothing is installed per user)
set -euo pipefail

REPO_URL="https://github.com/laurajul/DH-Workshop"
REPO_DIR="$HOME/DH-Workshop"
SHARED_DIR="/srv/shared/DSI-Workshop"
ENV_DIR="$SHARED_DIR/.venv"          # prebuilt environment (uploaded via azcopy)
ENV_PYTHON="$ENV_DIR/bin/python"
DATA_LINK="$HOME/data"
KERNEL_NAME="dh-workshop"

# --- checks -----------------------------------------------------------------
if [ ! -d "$SHARED_DIR" ]; then
    echo "ERROR: $SHARED_DIR does not exist. Please ask the workshop team for help." >&2
    exit 1
fi
if [ ! -x "$ENV_PYTHON" ]; then
    echo "ERROR: $ENV_PYTHON not found or not executable." >&2
    echo "       The shared environment is missing or broken. Please ask the workshop team." >&2
    exit 1
fi
if ! "$ENV_PYTHON" -c "import ipykernel" >/dev/null 2>&1; then
    echo "ERROR: the shared environment cannot run (ipykernel missing or python broken)." >&2
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
# Writes ~/.local/share/jupyter/kernels/dh-workshop/kernel.json, which points
# to the shared python. Re-running simply refreshes it.
echo ">>> Registering Jupyter kernel '$KERNEL_NAME' ..."
"$ENV_PYTHON" -m ipykernel install --user --name="$KERNEL_NAME" --display-name "$KERNEL_NAME"

echo
echo "Setup complete. Start your notebooks with the '$KERNEL_NAME' kernel."
