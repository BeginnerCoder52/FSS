Command:
python tools/frt_test/frt_test_runner.py --mode video --input video/260625_checkin_apple.mkv --stage all --motion-threshold 20 --stage1-fps 4

# FRT Test Summary

- Status: complete
- Session: `/home/richardmelvin52/FSS/frt_test_runs/20260625_231413`
- Mode: `video`
- Stage request: `all`
- Source: `video/260625_checkin_apple.mkv`

## Stages

- `stage1_mog2`: complete
  target_fps=4.0 processed=69 selected=35 skipped=34
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/stage1_mog2`
- `stage2_yolo`: complete
  frames=35 detections=18 runtime=ai_edge_litert
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/stage2_yolo`
- `stage3_bytetrack`: complete
  tracks=3 lost_events=2 id_switch_candidates=0
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/stage3_bytetrack`
- `stage4_linecross`: complete
  events=3 in=3 out=0
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/stage4_linecross`

## Final Artifacts

- `/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/final_report.json`
- `/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/final_summary.md`
- `/home/richardmelvin52/FSS/frt_test_runs/20260625_231413/final_stage_status.csv`
