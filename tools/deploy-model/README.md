## Deploy Model Tools

This folder contains 4 scripts:

- `tools/deploy-model/setup.sh`
- `tools/deploy-model/setup_python.sh`
- `tools/deploy-model/test-cases.sh`
- `tools/deploy-model/test-inference.py`

The previous README described CLI options for `test-cases.sh`, but that script currently uses fixed values and does not parse CLI arguments.

## 1) System Setup (`setup.sh`)

Run without arguments to perform base machine setup:

```bash
bash tools/deploy-model/setup.sh
```

Default actions:

1. `apt update && apt full-upgrade`
2. Install base tools: `htop curl wget git`
3. Create folders:
  - `fss-test/models`
  - `fss-test/test-images`
4. Disable unnecessary services:
  - `bluetooth`
  - `hciuart`
  - `ModemManager.service`

Optional flags:

- `--download-models`: download two models into `./fss-test/models/`
  - `model_int8.tflite`
  - `model_fp32.tflite`
- `--disable-swap`: remove swapfile and configure `zram-tools`
- `--force-cpu`: set CPU governor to performance and write Pi overclock config

Examples:

```bash
bash tools/deploy-model/setup.sh --download-models
bash tools/deploy-model/setup.sh --disable-swap
bash tools/deploy-model/setup.sh --force-cpu
```

## 2) Python Setup (`setup_python.sh`)

```bash
bash tools/deploy-model/setup_python.sh
```

What it does:

1. Install `uv`
2. Install Python `3.11.5`
3. Create and activate virtual environment at `./fss-test/.venv`
4. Install packages:
  - `tflite-runtime`
  - `opencv-python-headless`
  - `numpy<2`

## 3) Automated Batch Runner (`test-cases.sh`)

```bash
bash tools/deploy-model/test-cases.sh
```

This script is fixed-config (no CLI options) and runs 3 jobs in sequence:

1. INT8 benchmark with threads `1,2,4`
2. FP32 benchmark with threads `1,2,4`
3. FP16 single run with `--num-threads 4`

Current hardcoded paths inside script:

- Image dir: `test-images/images`
- Labels dir: `test-images/labels`
- Output root: `benchmark_results`
- Models:
  - `models/best_int8.tflite`
  - `models/best_fp32.tflite`
  - `models/best_fp16.tflite`

If a model file is missing, that step is skipped with a warning.

## 4) Direct Inference/Benchmark (`test-inference.py`)

You can run this script directly for custom experiments:

```bash
python tools/deploy-model/test-inference.py --model models/model_int8.tflite --image-dir test-images
```

Supported image extensions:

- `.jpg`
- `.jpeg`
- `.png`
- `.bmp`

CLI options:

| Option | Default | Description |
|---|---|---|
| `--model` | `models/model_int8.tflite` | TFLite model path |
| `--image-dir` | `test-images` | Test image directory (or dataset root containing `images/`) |
| `--labels-dir` | empty | YOLO label directory; if empty, script auto-detects from dataset |
| `--output-dir` | `results` | Output root folder |
| `--conf` | `0.5` | Confidence threshold |
| `--eval-iou` | `0.5` | IoU threshold for eval (`mAP50`) |
| `--num-threads` | `2` | TFLite threads for single run |
| `--benchmark-num-threads` | empty | Comma-separated thread list, e.g. `1,2,4` |
| `--debug` | off | Enable debug logs |
| `--auto-disable-debug` | off | Disable debug after first image |

Notes on image/label auto-detection:

1. If no image files are found directly in `--image-dir`, script tries `--image-dir/images`.
2. If `--labels-dir` is empty, script tries:
  - `--image-dir/labels`
  - sibling `labels` folder of active image dir
3. If labels dir is not found, evaluation metrics are skipped and speed-only benchmark is performed.

## Output Files

Each run creates a timestamped folder:

- `<output-dir>/run_YYYYMMDD_HHMMSS/`

Typical files:

- `results_<model>_t<threads>.csv` (per-image detections + timing)
- `eval_per_class_<model>_t<threads>.csv` (when labels are available)
- `benchmark_summary_<model>.csv` (when running one or multiple thread configurations)

## Important Path Mismatch
Before running `test-cases.sh`, make sure model files are copied/renamed to the expected paths, or update variables in `test-cases.sh`.
