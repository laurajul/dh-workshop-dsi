#!/bin/bash
#SBATCH --job-name=dsi_pipeline
#SBATCH --gpus=H100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=48:00:00
#SBATCH --output=/scratch/%u/logs/%x_%A.out
#SBATCH --error=/scratch/%u/logs/%x_%A.out
#
# The whole dataset pipeline in ONE job, in order:
#   0. CLIP weights   downloaded to $DATA/models/ViT-B-32.pt if not present
#   1. harvest        metadata records from the Europeana Search API          (about 2.5 h for the 9.5 GB selection)
#   2. embed          every shard in turn: images streamed into CLIP, vectors kept   (about 38 h at 50 requests/s)
#   3. merge          metadata.csv + embeddings/clip_vit_b32.npz, trimmed to MAX_GB
#
# Every step skips what is already done (finished institutions, finished shards, existing weights), so if the job
# runs out of time you simply submit it again. Set the --time above to your cluster's maximum. Before a job with
# less than MIN_SHARD_MINUTES left would start another shard, it stops cleanly and tells you to resubmit
# (or resubmits itself, with AUTO_RESUBMIT=1).
#
# One-time:   mkdir -p /scratch/$USER/logs      (sbatch does not create the log folder)
# Run from the repository root:   sbatch scripts/slurm/pipeline.sbatch
# Test first (about 10,000 images, an hour or so):
#   DATA=/scratch/$USER/dsi-test BUDGET_GB=0.016 MARGIN=1.0 SHARD_SIZE=3000 THUMB_RATE=15 sbatch scripts/slurm/pipeline.sbatch
#
# Settings (environment variables, all optional):
#   DATA=/scratch/$USER/dsi-workshop   output folder
#   BUDGET_GB=9.5  MARGIN=1.1          selection size; MAX_GB=9.5 is the final size limit
#   SHARD_SIZE=50000                   images per shard
#   THUMB_RATE=50                      requests per second to Europeana's thumbnail service (total, one job)
#   WORKERS=32                         download/preprocess workers
#   HARVEST_ARGS="--rate 6"            extra options for the harvest stage
#   MIN_SHARD_MINUTES=75  AUTO_RESUBMIT=0
#   EUROPEANA_API_KEY=...              or put the key in misc/api-key-europeana.txt
set -euo pipefail

# --- environment: edit for your cluster -------------------------------------------------------------------
# module load Python/3.12 CUDA
# source "$HOME/venvs/dh-workshop/bin/activate"      # needs torch, numpy, pillow, requests and the `clip` package
PYTHON="${PYTHON:-python}"
# -----------------------------------------------------------------------------------------------------------

REPO="${REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
DATA="${DATA:-/scratch/${USER}/dsi-workshop}"
BUDGET_GB="${BUDGET_GB:-9.5}"
MARGIN="${MARGIN:-1.1}"
MAX_GB="${MAX_GB:-9.5}"
SHARD_SIZE="${SHARD_SIZE:-50000}"
THUMB_RATE="${THUMB_RATE:-50}"
WORKERS="${WORKERS:-32}"
MIN_SHARD_MINUTES="${MIN_SHARD_MINUTES:-75}"
AUTO_RESUBMIT="${AUTO_RESUBMIT:-0}"

cd "$REPO"
mkdir -p "$DATA" "$DATA/models"
BUILD="$PYTHON scripts/build_dataset.py"
stamp() { date '+%Y-%m-%d %H:%M:%S'; }

# seconds left in this job (a very large number outside SLURM, so the script also runs by hand)
seconds_left() {
    local t
    t="$(squeue -h -j "${SLURM_JOB_ID:-}" -o %L 2>/dev/null || true)"
    [ -z "$t" ] && { echo 999999999; return; }
    [ "$t" = "UNLIMITED" ] && { echo 999999999; return; }
    local d=0 hms="$t"
    case "$t" in *-*) d="${t%%-*}"; hms="${t#*-}";; esac
    IFS=: read -r a b c <<<"$hms"
    if [ -z "${c:-}" ]; then echo $(( 10#$d * 86400 + 10#${a:-0} * 60 + 10#${b:-0} )); else echo $(( 10#$d * 86400 + 10#$a * 3600 + 10#$b * 60 + 10#$c )); fi
}

echo "[$(stamp)] dsi_pipeline: repo=$REPO data=$DATA budget=${BUDGET_GB} GB (final limit ${MAX_GB} GB)"
http_code="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' https://api.europeana.eu/thumbnail/v2/url.json || true)"
if [ -z "$http_code" ] || [ "$http_code" = "000" ]; then
    echo "error: api.europeana.eu is not reachable from this node (the harvest and the image requests need internet access)." >&2; exit 1
fi

# --- 0. CLIP weights -------------------------------------------------------------------------------------
if [ -f "$DATA/models/ViT-B-32.pt" ]; then
    echo "[$(stamp)] 0/3 CLIP weights present: $DATA/models/ViT-B-32.pt"
else
    echo "[$(stamp)] 0/3 downloading the CLIP ViT-B/32 weights (about 340 MB) to $DATA/models"
    "$PYTHON" -c "import clip; clip.load('ViT-B/32', device='cpu', download_root='$DATA/models'); print('ok')"
    [ -f "$DATA/models/ViT-B-32.pt" ] || { echo "error: the CLIP download did not produce ViT-B-32.pt" >&2; exit 1; }
fi

# --- 1. harvest ------------------------------------------------------------------------------------------
echo "[$(stamp)] 1/3 harvest (skips institutions that are already done)"
# shellcheck disable=SC2086
$BUILD plan    --out "$DATA" --budget-gb "$BUDGET_GB" --margin "$MARGIN" ${HARVEST_ARGS:-}
# shellcheck disable=SC2086
$BUILD harvest --out "$DATA" --budget-gb "$BUDGET_GB" --margin "$MARGIN" ${HARVEST_ARGS:-}

# --- 2. embed, shard by shard ----------------------------------------------------------------------------
records="$DATA/harvest/records.jsonl"
n_records=$(wc -l < "$records")
shards=$(( (n_records + SHARD_SIZE - 1) / SHARD_SIZE ))
parts="$DATA/embeddings/parts"
if ls "$parts"/part_*.npz >/dev/null 2>&1 && ! ls "$parts"/part_*_of_"$(printf '%05d' "$shards")".npz >/dev/null 2>&1; then
    echo "error: $parts has shard files made with a different number of shards than the $shards needed now" \
         "(SHARD_SIZE or the harvest changed). Use the old SHARD_SIZE, or delete $parts and $DATA/metadata_parts." >&2
    exit 1
fi
echo "[$(stamp)] 2/3 embed: $n_records records -> $shards shards of $SHARD_SIZE, $THUMB_RATE thumbnail requests/s"

started=0
for ((s = 0; s < shards; s++)); do
    part="$(printf '%05d_of_%05d' "$s" "$shards")"
    if [ -f "$parts/part_$part.npz" ] && [ -f "$DATA/metadata_parts/part_$part.csv" ]; then
        continue
    fi
    if [ "$(seconds_left)" -lt $(( MIN_SHARD_MINUTES * 60 )) ]; then
        echo "[$(stamp)] less than ${MIN_SHARD_MINUTES} minutes left: stopping before shard $s of $shards."
        if [ "$AUTO_RESUBMIT" = "1" ] && [ "$started" -gt 0 ]; then
            echo "[$(stamp)] AUTO_RESUBMIT=1: submitting the pipeline again."
            sbatch --export=ALL "$REPO/scripts/slurm/pipeline.sbatch"
        else
            echo "Resubmit with:  sbatch scripts/slurm/pipeline.sbatch   (finished shards are skipped)"
        fi
        exit 0
    fi
    echo "[$(stamp)] shard $s of $shards"
    $BUILD embed --out "$DATA" --models "$DATA/models" --shard "$s" --shards "$shards" \
        --workers "$WORKERS" --thumb-rate "$THUMB_RATE" | (grep -v '^  [0-9,]*/' || true)
    started=$((started + 1))
done

# --- 3. merge --------------------------------------------------------------------------------------------
echo "[$(stamp)] 3/3 merge and trim to ${MAX_GB} GB"
$BUILD merge --out "$DATA" --max-gb "$MAX_GB"
ls -la "$DATA/metadata.csv" "$DATA/embeddings/clip_vit_b32.npz"
echo "[$(stamp)] done. Copy these two files to the workshop folder (data/DSI-Workshop/)."
