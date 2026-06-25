# FRT Test Tools

Offline/live staged test tools for `frt_app`. These scripts only write debug
artifacts under `frt_test_runs/` and do not modify the runtime FRTApp pipeline.

## Run All Stages

Video input (hỗ trợ `.mp4`, `.mkv`, `.avi`, `.mov` và mọi định dạng OpenCV/FFmpeg có thể đọc):

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --input path/to/video.mkv \
  --stage all
```

Stage 1 is limited to `5 FPS` by default to match the FRTApp processing rate.
Override with `--stage1-fps`, or use `--stage1-fps 0` to disable this limiter.

Live camera input:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode live \
  --camera /dev/video0 \
  --stage all \
  --max-frames 300 \
  --stage1-fps 5
```

Each run creates:

```text
frt_test_runs/YYYYMMDD_HHMMSS/
├── stage1_mog2/
├── stage2_yolo/
├── stage3_bytetrack/
├── stage4_linecross/
├── final_report.json
└── final_summary.md
```

## Run One Stage

Stage 1 only:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --input path/to/video.mkv \
  --stage 1
```

Stage 2 on an existing session:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --input path/to/video.mkv \
  --session-dir frt_test_runs/YYYYMMDD_HHMMSS \
  --stage 2
```

Stage 3 with an explicit detections file:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --input path/to/video.mkv \
  --stage 3 \
  --detections frt_test_runs/YYYYMMDD_HHMMSS/stage2_yolo/detections.json
```

Stage 4 with a virtual line:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --input path/to/video.mkv \
  --stage 4 \
  --tracks frt_test_runs/YYYYMMDD_HHMMSS/stage3_bytetrack/tracks.json \
  --line-type horizontal \
  --line-pos 0.66
```

`--line-pos` is normalized by default. Values greater than `1.0` are treated as
pixel coordinates and normalized using the visualization frame size.

## Direct Stage Scripts

```bash
python tools/frt_test/stage1_mog2.py --input path/to/video.mkv --output-dir /tmp/stage1 --target-fps 5
python tools/frt_test/stage2_yolo_infer.py --selected-frames /tmp/stage1/selected_frames --output-dir /tmp/stage2
python tools/frt_test/stage3_bytetrack.py --detections /tmp/stage2/detections.json --output-dir /tmp/stage3
python tools/frt_test/stage4_linecross.py --tracks /tmp/stage3/tracks.json --output-dir /tmp/stage4
```

## Stage 2 Dataset Evaluation

Run model evaluation directly on a YOLO dataset image/label pair, without Stage 1:

```bash
python tools/frt_test/frt_test_runner.py \
  --mode video \
  --stage 2 \
  --image-dir path/to/dataset/images \
  --labels-dir path/to/dataset/labels \
  --eval-iou-threshold 0.5
```

If `images/` and `labels/` are sibling directories, `--labels-dir` can be omitted.
Stage 2 writes `eval_summary.json` and `eval_matches.csv` when labels are found.

YOLO runtime preference is `ai_edge_litert`. If the existing C TFLite reader is
used as fallback, `stage2_yolo/model_summary.json` and `final_report.json`
record that explicitly.
