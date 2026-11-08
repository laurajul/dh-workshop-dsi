#!/bin/bash
#SBATCH --job-name=dsi_harvest
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/%u/logs/%x_%A.out
#SBATCH --error=/scratch/%u/logs/%x_%A.out
#
# Stage 1 of 3: collect the metadata records from the Europeana Search API (no GPU needed).
# About 13,000 requests for the default selection (Europeana's Art collection, images only, 1.26 million records),
# throttled to 8 per second: about 30 minutes. Other selections: build_dataset.py options such as --theme.
# Resumable: if the job hits the time limit, submit it again and it continues where it stopped.
#
# One-time: mkdir -p /scratch/$USER/logs   (sbatch does not create the folder for the log files)
# Run from the repository root:   sbatch scripts/slurm/harvest.sbatch
# Settings (environment variables, all optional):
#   DATA=/scratch/$USER/dsi-workshop   output folder (shared by all three stages)
#   BUDGET_GB=9.5 MARGIN=1.1           size budget; harvest MARGIN times more, merge trims to the budget
#   HARVEST_ARGS="--rate 6"            any further build_dataset.py options
#   EUROPEANA_API_KEY=...              or put the key in misc/api-key-europeana.txt
set -euo pipefail

# --- environment: edit for your cluster -------------------------------------------------------------------
# module load Python/3.12
# source "$HOME/venvs/dh-workshop/bin/activate"
PYTHON="${PYTHON:-python}"
# -----------------------------------------------------------------------------------------------------------

REPO="${REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
DATA="${DATA:-/scratch/${USER}/dsi-workshop}"
BUDGET_GB="${BUDGET_GB:-9.5}"
MARGIN="${MARGIN:-1.1}"

mkdir -p "$DATA"
cd "$REPO"
[ -f scripts/build_dataset.py ] || { echo "error: $REPO is not the repository root (scripts/build_dataset.py not found). Run sbatch from the repository root." >&2; exit 1; }
echo "harvest: repo=$REPO data=$DATA budget=${BUDGET_GB} GB margin=$MARGIN"

# shellcheck disable=SC2086
"$PYTHON" scripts/build_dataset.py plan    --out "$DATA" --budget-gb "$BUDGET_GB" --margin "$MARGIN" ${HARVEST_ARGS:-}
# shellcheck disable=SC2086
"$PYTHON" scripts/build_dataset.py harvest --out "$DATA" --budget-gb "$BUDGET_GB" --margin "$MARGIN" ${HARVEST_ARGS:-}

echo "records: $(wc -l < "$DATA/harvest/records.jsonl")"
echo "next: scripts/slurm/submit_embed.sh"
