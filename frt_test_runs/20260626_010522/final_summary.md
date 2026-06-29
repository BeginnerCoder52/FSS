Command
python tools/frt_test/frt_test_runner.py --mode video --input video/260625_checkin_egg.mkv --stage all --motion-threshold 20 --stage1-fps 4

# FRT Test Summary

- Status: complete
- Session: `/home/richardmelvin52/FSS/frt_test_runs/20260626_010522`
- Mode: `video`
- Stage request: `all`
- Source: `video/260625_checkin_egg.mkv`

## Stages

- `stage1_mog2`: complete
  target_fps=4.0 processed=287 selected=228 skipped=59
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/stage1_mog2`
- `stage2_yolo`: complete
  frames=228 detections=86 runtime=ai_edge_litert
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/stage2_yolo`
- `stage3_bytetrack`: complete
  tracks=9 lost_events=12 id_switch_candidates=0
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/stage3_bytetrack`
- `stage4_linecross`: complete
  events=4 in=4 out=0
  output=`/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/stage4_linecross`

## Final Artifacts

- `/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/final_report.json`
- `/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/final_summary.md`
- `/home/richardmelvin52/FSS/frt_test_runs/20260626_010522/final_stage_status.csv`
