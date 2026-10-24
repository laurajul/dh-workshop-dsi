#!/usr/bin/env bash
# DH Workshop — Linux setup script
set -euo pipefail

REPO_URL="https://github.com/laurajul/DH-Workshop.git"
PROJECT_DIR="$HOME/DH-Workshop"
PYTHON_VERSION="3.11"
KERNEL_NAME="dh-workshop"
KERNEL_DISPLAY="DH Workshop"

# ─── helpers ──────────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { echo; echo "── $* ──────────────────────────────────────────────"; }

echo
echo "=============================================="
echo "  DH Workshop — Linux Setup"
echo "=============================================="

# ── 1. Git ────────────────────────────────────────────────────────────────────
step "Checking for Git"
if ! command -v git &>/dev/null; then
    echo "Git not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y git
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y git
    elif command -v yum &>/dev/null; then
        sudo yum install -y git
    else
        red "Could not install git automatically."
        red "Please install git with your package manager, then re-run this script."
        exit 1
    fi
fi
green "✓ git: $(git --version)"

# ── 2. curl (needed for uv installer) ────────────────────────────────────────
if ! command -v curl &>/dev/null; then
    echo "Installing curl..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y curl
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y curl
    elif command -v yum &>/dev/null; then
        sudo yum install -y curl
    fi
fi

# ── 3. uv ─────────────────────────────────────────────────────────────────────
step "Checking for uv"
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv &>/dev/null; then
    red "uv still not found after install. Please close this terminal,"
    red "open a new one, and re-run the script."
    exit 1
fi
green "✓ uv: $(uv --version)"

# ── 4. Clone repository ───────────────────────────────────────────────────────
step "Getting the workshop repository"
if [ -d "$PROJECT_DIR/.git" ]; then
    green "✓ Repository already exists at $PROJECT_DIR"
    cd "$PROJECT_DIR"
    git pull --ff-only 2>/dev/null || yellow "  (could not pull latest — continuing with existing version)"
else
    echo "Cloning to $PROJECT_DIR ..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ── 5. Python environment ─────────────────────────────────────────────────────
step "Setting up Python $PYTHON_VERSION environment"
uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION"
green "✓ Virtual environment created"

# ── 6. Install packages ───────────────────────────────────────────────────────
step "Installing Python packages (this may take a few minutes)"
uv pip install -r requirements.txt
green "✓ Packages installed"

# ── 7. Register Jupyter kernel ────────────────────────────────────────────────
step "Registering Jupyter kernel"
uv run python -m ipykernel install --user \
    --name="$KERNEL_NAME" \
    --display-name="$KERNEL_DISPLAY"
green "✓ Kernel '$KERNEL_DISPLAY' registered"

# ── 8. Done — launch JupyterLab ───────────────────────────────────────────────
echo
echo "=============================================="
green "  ✓ Setup complete!"
echo "=============================================="
echo
echo "  JupyterLab is opening in your browser."
echo "  When a notebook is open, select the"
echo "  '$KERNEL_DISPLAY' kernel in the top-right corner."
echo
uv run jupyter lab
