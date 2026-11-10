#!/usr/bin/env bash
# DH-Workshop setup – run once at the beginning of the workshop.
#   1. clones the workshop repository into ~/DH-Workshop
#   2. creates a uv environment in ~/shared and installs requirements.txt
#   3. registers a Jupyter kernel called "dh-workshop"
set -euo pipefail

REPO_URL="https://github.com/laurajul/DH-Workshop"
REPO_DIR="$HOME/DH-Workshop"
SHARED_DIR="$HOME/shared"

# --- checks -----------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: 'uv' was not found. Please ask the workshop team for help." >&2
    exit 1
fi
if [ ! -d "$SHARED_DIR" ]; then
    echo "ERROR: $SHARED_DIR does not exist." >&2
    exit 1
fi

# --- 1. clone repository into home ------------------------------------------
if [ -d "$REPO_DIR/.git" ]; then
    echo ">>> Repository already exists at $REPO_DIR, skipping clone."
else
    echo ">>> Cloning $REPO_URL into $REPO_DIR ..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# --- 2. uv environment in shared --------------------------------------------
cd "$SHARED_DIR"

# Use requirements.txt from shared; fall back to the one in the cloned repo.
if [ -f "$SHARED_DIR/requirements.txt" ]; then
    REQ_FILE="$SHARED_DIR/requirements.txt"
elif [ -f "$REPO_DIR/requirements.txt" ]; then
    REQ_FILE="$REPO_DIR/requirements.txt"
else
    echo "ERROR: requirements.txt not found in $SHARED_DIR or $REPO_DIR." >&2
    exit 1
fi

if [ ! -f "$SHARED_DIR/pyproject.toml" ]; then
    echo ">>> Initialising uv project in $SHARED_DIR ..."
    uv init --bare
fi

echo ">>> Installing dependencies from $REQ_FILE ..."
uv add -r "$REQ_FILE"

# --- 3. Jupyter kernel -------------------------------------------------------
echo ">>> Registering Jupyter kernel 'dh-workshop' ..."
uv run python -m ipykernel install --user --name=dh-workshop --display-name "dh-workshop"

echo
echo "Setup complete. Start your notebooks with the 'dh-workshop' kernel."
