#!/bin/bash
#SBATCH --job-name=dsi_embed
#SBATCH --gpus=H100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=/scratch/%u/logs/%x_%A_%a.out
#SBATCH --error=/scratch/%u/logs/%x_%A_%a.out
#
# Stage 2 of 3: one array task per shard. Each task streams its images (about 50,000) into CLIP and keeps
# only the vectors and the URL that served each image. Nothing is stored except two small part files.
#
# Do not call sbatch on this file directly; use scripts/slurm/submit_embed.sh, which sets the array size.
# (Direct use:  sbatch --array=0-25%2 --export=ALL,SHARDS=26 scripts/slurm/embed.sbatch)
#
# Resumable: a finished shard leaves part files and is skipped, so resubmitting the same array only
# redoes the shards that failed.
#
# Settings (environment variables):
#   DATA=/scratch/$USER/dsi-workshop   same folder as the harvest
#   SHARDS=26                          total number of shards (must equal the array size)
#   THUMB_RATE=25                      Europeana thumbnail requests per second PER JOB. The total load on
#                                      Europeana is THUMB_RATE times the number of jobs running at once
#                                      (the "%2" in the array), 25 x 2 = 50 requests/s by default.
#   WORKERS=32                         download/preprocess workers
set -euo pipefail

REPO="${REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"

# Python: the uv environment in the repository root (create it once: uv venv && uv pip install -r requirements.txt).
# Set PYTHON=/path/to/python to use another interpreter.
PYTHON="${PYTHON:-$REPO/.venv/bin/python}"
if [ ! -x "$PYTHON" ] || ! "$PYTHON" -c "import torch, clip, numpy, PIL, requests" 2>/dev/null; then
    echo "error: $PYTHON is missing or cannot import torch, clip, numpy, PIL, requests." >&2
    echo "Create the environment once, from the repository root:  uv venv && uv pip install -r requirements.txt" >&2
    exit 1
fi
DATA="${DATA:-/scratch/${USER}/dsi-workshop}"
SHARDS="${SHARDS:?SHARDS is not set; submit with scripts/slurm/submit_embed.sh}"
SHARD="${SLURM_ARRAY_TASK_ID:?this script is meant to run as an array job}"
THUMB_RATE="${THUMB_RATE:-25}"
WORKERS="${WORKERS:-32}"

cd "$REPO"
[ -f scripts/build_dataset.py ] || { echo "error: $REPO is not the repository root (scripts/build_dataset.py not found). Run sbatch from the repository root." >&2; exit 1; }
[ -f "$DATA/harvest/records.jsonl" ] || { echo "No $DATA/harvest/records.jsonl: run harvest.sbatch first." >&2; exit 1; }
[ -f "$DATA/models/ViT-B-32.pt" ] || { echo "No CLIP weights: run scripts/slurm/get_clip_weights.sh first." >&2; exit 1; }
http_code="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' https://api.europeana.eu/thumbnail/v2/url.json || true)"
[ "$http_code" != "000" ] && [ -n "$http_code" ] \
    || echo "warning: could not reach api.europeana.eu from this node (compute nodes may have no internet)" >&2

gpu="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)" || gpu=""
case "$gpu" in ""|*failed*|*NVIDIA-SMI*) gpu="no GPU found (running on the CPU)";; esac
echo "embed: shard $SHARD of $SHARDS on $(hostname), $gpu"
"$PYTHON" scripts/build_dataset.py embed --out "$DATA" --models "$DATA/models" \
    --shard "$SHARD" --shards "$SHARDS" --workers "$WORKERS" --thumb-rate "$THUMB_RATE"
