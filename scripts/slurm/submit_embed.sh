#!/usr/bin/env bash
# Submit the embedding array job and, after it, the merge job.
#
# Run from the repository root after the harvest has finished:
#     scripts/slurm/submit_embed.sh
#
# Settings (environment variables, all optional):
#   DATA=/scratch/$USER/dsi-workshop   folder with harvest/records.jsonl and models/ViT-B-32.pt
#   SHARD_SIZE=50000                   images per shard (one array task each)
#   MAX_PARALLEL=2                     shards running at once; with THUMB_RATE this sets the load on Europeana
#   THUMB_RATE=25                      thumbnail requests per second per job (total = MAX_PARALLEL x THUMB_RATE)
#
# Small test first (about 10,000 images, minutes instead of days):
#   DATA=/scratch/$USER/dsi-test BUDGET_GB=0.016 MARGIN=1.0 sbatch scripts/slurm/harvest.sbatch
#   DATA=/scratch/$USER/dsi-test SHARD_SIZE=3000 scripts/slurm/submit_embed.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DATA="${DATA:-/scratch/${USER}/dsi-workshop}"
SHARD_SIZE="${SHARD_SIZE:-50000}"
MAX_PARALLEL="${MAX_PARALLEL:-2}"
export THUMB_RATE="${THUMB_RATE:-25}"
export REPO="${REPO:-$PWD}"

[ -f scripts/build_dataset.py ] || { echo "Run this from the repository root (scripts/build_dataset.py not found in $PWD)." >&2; exit 1; }
records="$DATA/harvest/records.jsonl"
[ -f "$records" ] || { echo "No $records: run 'sbatch scripts/slurm/harvest.sbatch' first." >&2; exit 1; }
"$here/get_clip_weights.sh" "$DATA"                      # downloads the CLIP weights if they are not there yet

n=$(wc -l < "$records")
shards=$(( (n + SHARD_SIZE - 1) / SHARD_SIZE ))
mkdir -p "/scratch/${USER}/logs" 2>/dev/null || true      # sbatch needs this folder for the log files
echo "$n records -> $shards shards of $SHARD_SIZE, $MAX_PARALLEL at a time, $THUMB_RATE thumbnail requests/s per job"
echo "Europeana thumbnail load: about $(( MAX_PARALLEL * THUMB_RATE )) requests/s in total"

embed_id=$(sbatch --parsable --array="0-$((shards - 1))%${MAX_PARALLEL}" --export=ALL,SHARDS="$shards" "$here/embed.sbatch")
merge_id=$(sbatch --parsable --dependency="afterok:${embed_id}" --export=ALL "$here/merge.sbatch")
echo "embed array: $embed_id   merge (after all shards succeed): $merge_id"
echo "If some shards fail, run this script again: finished shards are skipped, and the merge job is queued anew."
