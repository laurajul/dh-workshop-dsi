# Building the dataset on a SLURM cluster

Wraps `scripts/build_dataset.py` in batch jobs. Result: `metadata.csv` and `embeddings/clip_vit_b32.npz`, together
at most 9.5 GB. No images are stored; each image is streamed into CLIP and discarded.

| Stage | Script | Resources | Time (9.5 GB selection) |
|---|---|---|---|
| 1. harvest metadata | `harvest.sbatch` | 4 CPUs, 16 GB, no GPU | about 2.5 h, resumable |
| 2. embed (array job) | `embed.sbatch`, submitted by `submit_embed.sh` | 1 GPU, 16 CPUs, 32 GB per task | about 138 shards, roughly 35 h at the default Europeana load |
| 3. merge and trim | `merge.sbatch` | 4 CPUs, 48 GB | minutes |

## One-time setup

1. Clone the repository on the cluster, and from now on run everything from its root.
2. Python environment with `torch`, `numpy`, `pillow`, `requests` and the `clip` package (`pip install git+https://github.com/openai/CLIP.git`). Activate it in the marked lines at the top of each `.sbatch` file, or set `PYTHON=/path/to/python`.
3. API key: `misc/api-key-europeana.txt`, or `export EUROPEANA_API_KEY=...`.
4. CLIP weights: `mkdir -p $DATA/models && cp ViT-B-32.pt $DATA/models/` (the file is `models/CLIP/ViT-B-32.pt` in your working copy).
5. `mkdir -p /scratch/$USER/logs` (sbatch does not create the log folder).

`DATA` defaults to `/scratch/$USER/dsi-workshop`. All scripts read it from the environment, so set it once: `export DATA=...`.

## Test first (about 10,000 images)

```bash
export DATA=/scratch/$USER/dsi-test
mkdir -p $DATA/models && cp ViT-B-32.pt $DATA/models/
BUDGET_GB=0.016 MARGIN=1.0 sbatch scripts/slurm/harvest.sbatch      # about 1,500 requests, a few minutes
# wait for it to finish, then:
SHARD_SIZE=3000 scripts/slurm/submit_embed.sh                       # 4 shards, then the merge job
```

## The real run

```bash
unset DATA                                   # or export DATA=/scratch/$USER/dsi-workshop
sbatch scripts/slurm/harvest.sbatch          # waits for the run to finish: tail -f /scratch/$USER/logs/dsi_harvest_*.out
scripts/slurm/submit_embed.sh                # counts the records, submits the array and the merge job
```

Copy the two output files (`$DATA/metadata.csv`, `$DATA/embeddings/clip_vit_b32.npz`) to `data/DSI-Workshop/`.

## Load on Europeana

Europeana publishes no quota for API keys. The harvest is throttled to 8 Search API requests per second (`--rate`). The embed stage requests one small image per record, mostly from Europeana's thumbnail service, so its load is

    THUMB_RATE (requests/s per job) x MAX_PARALLEL (shards running at once)

Defaults: 25 x 2 = 50 requests/s. Start the test run, look at the error counts in the logs ("without a usable image"), and change the rate only if it stays clean. `THUMB_RATE=10 MAX_PARALLEL=2 scripts/slurm/submit_embed.sh` halves the load and doubles the time. Compute nodes need internet access for this stage; the job prints a warning if `api.europeana.eu` is unreachable.

## When something fails

- **Harvest hits the time limit:** submit `harvest.sbatch` again. It continues with the institutions not finished yet.
- **Some shards fail:** run `submit_embed.sh` again. Finished shards leave part files and are skipped (they exit within a minute); only the failed ones do work. A new merge job is queued after the new array. The earlier merge job stays pending with `DependencyNeverSatisfied`: cancel it with `scancel`.
- **Merge reports more than 9.5 GB:** run `MAX_GB=9.3 sbatch scripts/slurm/merge.sbatch`.
- **Out of memory in the merge:** raise `--mem`; the vectors alone are about 6 GB.

## Settings reference

| Variable | Default | Used by |
|---|---|---|
| `DATA` | `/scratch/$USER/dsi-workshop` | all |
| `BUDGET_GB`, `MARGIN` | 9.5, 1.1 | harvest |
| `HARVEST_ARGS` | empty | harvest (extra `build_dataset.py` options) |
| `SHARD_SIZE`, `MAX_PARALLEL` | 50000, 2 | `submit_embed.sh` |
| `THUMB_RATE`, `WORKERS` | 25, 32 | embed |
| `MAX_GB` | 9.5 | merge |
| `PYTHON`, `REPO` | `python`, the directory you submit from | all |
