#!/bin/bash
#SBATCH --job-name=dsi_merge
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/%u/logs/%x_%A.out
#SBATCH --error=/scratch/%u/logs/%x_%A.out
#
# Stage 3 of 3: join the shard files into the final dataset and trim it to the size limit.
# Writes $DATA/metadata.csv and $DATA/embeddings/clip_vit_b32.npz (together at most MAX_GB).
# Needs about 6 GB of memory for the vectors, plus working space.
#
# submit_embed.sh submits this job to start after all embed tasks succeeded.
#   MAX_GB=9.5   size limit for metadata.csv + embeddings
set -euo pipefail

REPO="${REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"

# Python: the uv environment in the repository root (create it once: uv venv && uv pip install -r requirements.txt).
# Set PYTHON=/path/to/python to use another interpreter.
PYTHON="${PYTHON:-$REPO/.venv/bin/python}"
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -c "import numpy" 2>/dev/null; then
    echo "error: $PYTHON is missing or cannot import numpy." >&2
    echo "Create the environment once, from the repository root:  uv venv && uv pip install -r requirements.txt" >&2
    exit 1
fi
DATA="${DATA:-/scratch/${USER}/dsi-workshop}"
MAX_GB="${MAX_GB:-9.5}"

cd "$REPO"
[ -f scripts/build_dataset.py ] || { echo "error: $REPO is not the repository root (scripts/build_dataset.py not found). Run sbatch from the repository root." >&2; exit 1; }
"$PYTHON" scripts/build_dataset.py merge --out "$DATA" --max-gb "$MAX_GB"
ls -la "$DATA/metadata.csv" "$DATA/embeddings/clip_vit_b32.npz"
echo "Copy these two files to the workshop folder (data/DSI-Workshop/)."
