# Building the dataset on a SLURM cluster

Wraps `scripts/build_dataset.py` in batch jobs. Result: `metadata.csv` and `embeddings/clip_vit_b32.npz`, together
at most 9.5 GB. No images are stored; each image is streamed into CLIP and discarded.

The default selection is Europeana's **Art** thematic collection, images only (no books or other text), openly reusable: about 1.26 million images from 799 institutions, about 1.9 GB in the end, so the 9.5 GB limit does not cap any institution. Change the theme with `HARVEST_ARGS="--theme photography"` (or `--theme ""` for everything, which is 21 million images and does need the cap), and use a fresh `DATA` folder when you do.

## Two ways to run it

**One job (`pipeline.sbatch`)**: everything in order, in a single GPU job: CLIP weights are downloaded if missing, then harvest, embed (shard after shard) and merge. Simplest to start and to reason about; its defaults are the **half-size Art selection** (about 630,000 images, about 1 GB; `THEME=art BUDGET_GB=0.96 MARGIN=1.0 MAX_GB=0.96`), which takes about 4 hours at 50 requests/s (`--time` is 8 h). For the full Art collection set `BUDGET_GB=9.5 MARGIN=1.1 MAX_GB=9.5` (about 8 hours, raise `--time`). The separate stage scripts below still default to the 9.5 GB settings, so export those variables when you use them. Every step skips what is already done, so a job that runs out of time is continued by submitting the same command again. Before a shard that would not finish, the job stops cleanly (`MIN_SHARD_MINUTES`, default 75); with `AUTO_RESUBMIT=1` it resubmits itself.

```bash
mkdir -p /scratch/$USER/logs
sbatch scripts/slurm/pipeline.sbatch
# test first:  DATA=/scratch/$USER/dsi-test BUDGET_GB=0.016 MARGIN=1.0 SHARD_SIZE=3000 THUMB_RATE=15 sbatch scripts/slurm/pipeline.sbatch
```

**Separate stages**: the same steps as three scripts, with the embedding spread over an array job (below). Use this if several GPUs can work in parallel or you prefer short jobs. The Europeana load is the limit either way, not the GPU: 50 requests/s means roughly the same total time.

The rest of this file describes the separate stages; the setup, the load on Europeana and the failure notes apply to both.

| Stage | Script | Resources | Time (Art selection, 1.26 million images) |
|---|---|---|---|
| 1. harvest metadata | `harvest.sbatch` | 4 CPUs, 16 GB, no GPU | about 30 min, resumable |
| 2. embed (array job) | `embed.sbatch`, submitted by `submit_embed.sh` | 1 GPU, 16 CPUs, 32 GB per task | about 26 shards, roughly 7 h at the default Europeana load |
| 3. merge and trim | `merge.sbatch` | 4 CPUs, 48 GB | minutes |

## One-time setup

1. Clone the repository on the cluster. **Run every command from the repository root** (the folder that contains `scripts/`), not from `scripts/slurm/`.
2. Python environment: the uv environment in the repository root, which all the job scripts use automatically (`.venv/bin/python`; set `PYTHON=...` to use another one). Create it once, from the repository root, on the shared filesystem so the compute nodes can see it: `uv venv --python 3.12 && uv pip install -r requirements.txt`. The jobs stop immediately with a clear message if the environment is missing or lacks `torch`, `clip`, `numpy`, `pillow` or `requests`.
3. API key: `misc/api-key-europeana.txt`, or `export EUROPEANA_API_KEY=YOUR_KEY`.
4. CLIP weights: model files are not in git. `pipeline.sbatch` and `submit_embed.sh` download them if they are missing (`scripts/slurm/get_clip_weights.sh` does only that, with a checksum; it needs only curl or wget).
5. `mkdir -p /scratch/$USER/logs` (sbatch does not create the log folder).

`DATA` defaults to `/scratch/$USER/dsi-workshop`. All scripts read it from the environment, so set it once: `export DATA=...`.

## Test first (about 10,000 images)

```bash
export DATA=/scratch/$USER/dsi-test
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
| `MAX_GB` | 9.5 | merge, pipeline |
| `MIN_SHARD_MINUTES`, `AUTO_RESUBMIT` | 75, 0 | pipeline only |
| `PYTHON`, `REPO` | `python`, the directory you submit from | all |
