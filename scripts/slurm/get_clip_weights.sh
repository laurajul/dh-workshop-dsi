#!/usr/bin/env bash
# Download the CLIP ViT-B/32 weights (about 340 MB) to $DATA/models/ViT-B-32.pt, unless they are already there.
# Needs only curl or wget; the file is checked against OpenAI's published SHA-256.
#
#   scripts/slurm/get_clip_weights.sh                 # uses $DATA, default /scratch/$USER/dsi-workshop
#   scripts/slurm/get_clip_weights.sh /some/folder    # models go to /some/folder/models/
set -euo pipefail
DATA="${1:-${DATA:-/scratch/${USER}/dsi-workshop}}"
SHA=40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af
URL="https://openaipublic.azureedge.net/clip/models/$SHA/ViT-B-32.pt"
FILE="$DATA/models/ViT-B-32.pt"

check() { [ "$(sha256sum "$FILE" | cut -d' ' -f1)" = "$SHA" ]; }

mkdir -p "$DATA/models"
if [ -f "$FILE" ] && check; then
    echo "CLIP weights already present and verified: $FILE"; exit 0
fi
echo "Downloading CLIP ViT-B/32 to $FILE ..."
if command -v curl >/dev/null; then curl -fsSL --retry 3 -o "$FILE.part" "$URL"; else wget -q -O "$FILE.part" "$URL"; fi
mv "$FILE.part" "$FILE"
check || { echo "error: checksum of $FILE does not match, deleting it" >&2; rm -f "$FILE"; exit 1; }
echo "ok: $FILE"
