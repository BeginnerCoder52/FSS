#!/usr/bin/env bash
#
# Run the FRT video demo end-to-end on Raspberry Pi:
#   DBDaemon + MagicMirror + FRTApp + SHM video writer + mock door open/close.
#
# This script is intended for manual demos, not production boot.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FSS_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VIDEO_PATH="../video/260625_checkin_apple.mkv"
MODEL_PATH="/opt/fss/models/YOLOv11n_260518_best_int8.tflite"
FPS="10"
BOUNDARY_Y="0.66"
START_DELAY="3"
OPEN_DELAY="0.5"
SETTLE_AFTER_CLOSE="5"
VIDEO_SECONDS="0"
LOG_DIR="/tmp/fss_frt_video_demo_$(date +%Y%m%d_%H%M%S)"
START_MAGICMIRROR="1"
MAGICMIRROR_SCRIPT="start"
STOP_SYSTEMD="0"
REUSE_DBDAEMON="0"
USE_C_BACKEND="0"

CONFIDENCE="0.6"
LOW_CONFIDENCE="0.1"
IOU_THRESHOLD="0.5"
BYTETRACK_MAX_AGE="30"
BYTETRACK_MATCH_THRESH="0.6"
MOG2_VARIANCE="32.0"
MOG2_AREA_THRESHOLD="3.0"

PIDS=()
NAMES=()

usage() {
    cat <<EOF
Usage:
  bash tools/run_frt_video_demo.sh [options]

Options:
  --video PATH             Video file to stream into SHM.
                           Default: ${VIDEO_PATH}
  --model PATH             TFLite model path.
                           Default: ${MODEL_PATH}
  --fps N                  Video playback FPS. Default: ${FPS}
  --boundary-y RATIO       Virtual horizontal boundary ratio. Default: ${BOUNDARY_Y}
  --start-delay SEC        Delay before writer starts sending frames. Default: ${START_DELAY}
  --open-delay SEC         Delay between writer launch and DOOR_OPEN. Default: ${OPEN_DELAY}
  --video-seconds SEC      Stop video playback after SEC seconds. Default: full video.
  --settle SEC             Seconds to keep services alive after DOOR_CLOSE. Default: ${SETTLE_AFTER_CLOSE}
  --log-dir PATH           Log output directory. Default: ${LOG_DIR}
  --no-magicmirror         Do not start MagicMirror.
  --magicmirror-script N   npm script used to start MagicMirror.
                           Use start:x11, start:wayland, server, or start.
                           Default: ${MAGICMIRROR_SCRIPT}
  --stop-systemd           Stop fss-db/fss-ai/fss-camera/fss-sensor before starting demo.
  --reuse-dbdaemon         Do not start DBDaemon; use an already-running DBDaemon.
  --use-c-backend          Start FRTApp with --use-c-backend.
  
  AI & Tracking Tuning:
  --confidence N           YOLO high confidence (default: ${CONFIDENCE})
  --low-confidence N       YOLO low confidence (default: ${LOW_CONFIDENCE})
  --iou-threshold N        YOLO NMS IoU threshold (default: ${IOU_THRESHOLD})
  --bytetrack-max-age N    Max age for lost tracks (default: ${BYTETRACK_MAX_AGE})
  --bytetrack-match-thresh N ByteTrack IoU match threshold (default: ${BYTETRACK_MATCH_THRESH})
  --mog2-variance N        MOG2 variance threshold (default: ${MOG2_VARIANCE})
  --mog2-area-threshold N  MOG2 area %% (default: ${MOG2_AREA_THRESHOLD})
  -h, --help               Show this help.

Example:
  bash tools/run_frt_video_demo.sh \\
    --video ../video/260625_checkin_apple.mkv \\
    --model /opt/fss/models/YOLOv11n_260518_best_int8.tflite \\
    --fps 10 \\
    --boundary-y 0.66
EOF
}

log() {
    printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$*"
}

die() {
    log "ERROR: $*"
    exit 1
}

die_with_log() {
    local logfile="$1"
    shift
    log "ERROR: $*"
    if [[ -f "${logfile}" ]]; then
        log "Last 80 lines from ${logfile}:"
        tail -n 80 "${logfile}" || true
    else
        log "Log file does not exist yet: ${logfile}"
    fi
    exit 1
}

has_dbus_name() {
    local name="$1"
    command -v busctl >/dev/null 2>&1 || return 1
    busctl --system status "${name}" >/dev/null 2>&1
}

wait_for_dbus_name() {
    local name="$1"
    local timeout="${2:-20}"

    if ! command -v busctl >/dev/null 2>&1; then
        log "busctl not found; sleeping 3s instead of waiting for ${name}"
        sleep 3
        return 0
    fi

    local start
    start="$(date +%s)"
    while true; do
        if has_dbus_name "${name}"; then
            return 0
        fi

        local now
        now="$(date +%s)"
        if (( now - start >= timeout )); then
            return 1
        fi
        sleep 0.25
    done
}

python_for() {
    local component="$1"
    local candidate="${FSS_ROOT}/${component}/venv/bin/python"
    if [[ -x "${candidate}" ]]; then
        printf '%s\n' "${candidate}"
    else
        printf 'python3\n'
    fi
}

start_process() {
    local name="$1"
    local workdir="$2"
    local logfile="$3"
    shift 3

    log "Starting ${name}; log=${logfile}"
    (
        cd "${workdir}"
        exec "$@"
    ) >"${logfile}" 2>&1 &

    local pid=$!
    PIDS+=("${pid}")
    NAMES+=("${name}")
    log "${name} pid=${pid}"
}

cleanup() {
    local status=$?
    set +e

    if ((${#PIDS[@]} > 0)); then
        log "Stopping demo processes..."
        for ((idx=${#PIDS[@]}-1; idx>=0; idx--)); do
            local pid="${PIDS[$idx]}"
            local name="${NAMES[$idx]}"
            if kill -0 "${pid}" >/dev/null 2>&1; then
                log "TERM ${name} pid=${pid}"
                kill -TERM "${pid}" >/dev/null 2>&1
            fi
        done

        sleep 2

        for ((idx=${#PIDS[@]}-1; idx>=0; idx--)); do
            local pid="${PIDS[$idx]}"
            local name="${NAMES[$idx]}"
            if kill -0 "${pid}" >/dev/null 2>&1; then
                log "KILL ${name} pid=${pid}"
                kill -KILL "${pid}" >/dev/null 2>&1
            fi
        done
    fi

    if [[ "${START_MAGICMIRROR}" == "1" ]] && command -v pkill >/dev/null 2>&1; then
        local mm_pattern="electron.*js/electron.js"
        if pgrep -f "${mm_pattern}" >/dev/null 2>&1; then
            log "TERM MagicMirror Electron child processes"
            pkill -TERM -f "${mm_pattern}" >/dev/null 2>&1 || true
            sleep 1
        fi

        if pgrep -f "${mm_pattern}" >/dev/null 2>&1; then
            log "KILL MagicMirror Electron child processes"
            pkill -KILL -f "${mm_pattern}" >/dev/null 2>&1 || true
        fi
    fi

    log "Logs: ${LOG_DIR}"
    if [[ -d "${LOG_DIR}" ]]; then
        for logfile in \
            "${LOG_DIR}/video_writer.log" \
            "${LOG_DIR}/door_open.log" \
            "${LOG_DIR}/door_close.log" \
            "${LOG_DIR}/frt_app.log" \
            "${LOG_DIR}/db_daemon.log"; do
            if [[ -f "${logfile}" ]]; then
                log "Last 30 lines from ${logfile}:"
                tail -n 30 "${logfile}" || true
            fi
        done
    fi
    exit "${status}"
}

trap cleanup EXIT INT TERM

while (($#)); do
    case "$1" in
        --video)
            VIDEO_PATH="$2"
            shift 2
            ;;
        --model)
            MODEL_PATH="$2"
            shift 2
            ;;
        --fps)
            FPS="$2"
            shift 2
            ;;
        --boundary-y)
            BOUNDARY_Y="$2"
            shift 2
            ;;
        --start-delay)
            START_DELAY="$2"
            shift 2
            ;;
        --open-delay)
            OPEN_DELAY="$2"
            shift 2
            ;;
        --video-seconds)
            VIDEO_SECONDS="$2"
            shift 2
            ;;
        --settle)
            SETTLE_AFTER_CLOSE="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --no-magicmirror)
            START_MAGICMIRROR="0"
            shift
            ;;
        --magicmirror-script)
            MAGICMIRROR_SCRIPT="$2"
            shift 2
            ;;
        --stop-systemd)
            STOP_SYSTEMD="1"
            shift
            ;;
        --reuse-dbdaemon)
            REUSE_DBDAEMON="1"
            shift
            ;;
        --use-c-backend)
            USE_C_BACKEND="1"
            shift
            ;;
        --confidence) CONFIDENCE="$2"; shift 2 ;;
        --low-confidence) LOW_CONFIDENCE="$2"; shift 2 ;;
        --iou-threshold) IOU_THRESHOLD="$2"; shift 2 ;;
        --bytetrack-max-age) BYTETRACK_MAX_AGE="$2"; shift 2 ;;
        --bytetrack-match-thresh) BYTETRACK_MATCH_THRESH="$2"; shift 2 ;;
        --mog2-variance) MOG2_VARIANCE="$2"; shift 2 ;;
        --mog2-area-threshold) MOG2_AREA_THRESHOLD="$2"; shift 2 ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

mkdir -p "${LOG_DIR}"

DB_PY="$(python_for db_daemon)"
FRT_PY="$(python_for frt_app/py_ai_core)"

if [[ "${VIDEO_PATH}" != /* ]]; then
    VIDEO_PATH="${FSS_ROOT}/${VIDEO_PATH}"
fi

[[ -f "${VIDEO_PATH}" ]] || die "Video file not found: ${VIDEO_PATH}"
[[ -f "${MODEL_PATH}" ]] || log "WARNING: model file not found: ${MODEL_PATH}"

if [[ ! -w /opt/fss ]]; then
    log "WARNING: /opt/fss is not writable by $(id -un). LivePreview may fail."
    log "Fix on Pi: sudo chown -R $(id -un):$(id -gn) /opt/fss && chmod -R 775 /opt/fss"
fi

if [[ "${STOP_SYSTEMD}" == "1" ]]; then
    log "Stopping FSS systemd services for manual demo..."
    sudo systemctl stop fss-recommend fss-ai fss-camera fss-sensor fss-db 2>/dev/null || true
fi

if [[ "${REUSE_DBDAEMON}" == "0" ]] && has_dbus_name "vn.edu.uit.FSS.DBDaemon"; then
    die "vn.edu.uit.FSS.DBDaemon is already running. Stop it or pass --reuse-dbdaemon."
fi

if has_dbus_name "vn.edu.uit.FSS.FRTApp"; then
    die "vn.edu.uit.FSS.FRTApp is already running. Stop the existing FRTApp first."
fi

if has_dbus_name "vn.edu.uit.FSS.Sensor"; then
    die "vn.edu.uit.FSS.Sensor is already running. Stop SensorDaemon or pass --stop-systemd."
fi

log "FSS root: ${FSS_ROOT}"
log "Video: ${VIDEO_PATH}"
log "Model: ${MODEL_PATH}"
if [[ "${START_MAGICMIRROR}" == "1" ]]; then
    log "MagicMirror npm script: ${MAGICMIRROR_SCRIPT}"
fi
if [[ "${VIDEO_SECONDS}" != "0" ]]; then
    log "Video playback limit: ${VIDEO_SECONDS}s"
else
    log "Video playback limit: full video"
fi
log "Logs: ${LOG_DIR}"

if [[ "${REUSE_DBDAEMON}" == "0" ]]; then
    start_process \
        "DBDaemon" \
        "${FSS_ROOT}/db_daemon" \
        "${LOG_DIR}/db_daemon.log" \
        "${DB_PY}" "${FSS_ROOT}/db_daemon/src/main.py"

    wait_for_dbus_name "vn.edu.uit.FSS.DBDaemon" 20 \
        || die_with_log "${LOG_DIR}/db_daemon.log" \
            "DBDaemon did not register D-Bus name."
else
    log "Reusing existing DBDaemon."
fi

if [[ "${START_MAGICMIRROR}" == "1" ]]; then
    start_process \
        "MagicMirror" \
        "${FSS_ROOT}/electron_app/magicmirror" \
        "${LOG_DIR}/magicmirror.log" \
        npm run "${MAGICMIRROR_SCRIPT}"
    sleep 5
fi

FRT_ARGS=(
    "${FSS_ROOT}/frt_app/py_ai_core/src/main.py"
    --model "${MODEL_PATH}"
    --debug-no-distance
    --shm-only
    --debug-dir "${LOG_DIR}/debug_frames"
    --boundary-y "${BOUNDARY_Y}"
    --confidence "${CONFIDENCE}"
    --low-confidence "${LOW_CONFIDENCE}"
    --iou-threshold "${IOU_THRESHOLD}"
    --bytetrack-max-age "${BYTETRACK_MAX_AGE}"
    --bytetrack-match-thresh "${BYTETRACK_MATCH_THRESH}"
    --mog2-variance "${MOG2_VARIANCE}"
    --mog2-area-threshold "${MOG2_AREA_THRESHOLD}"
)

if [[ "${USE_C_BACKEND}" == "1" ]]; then
    FRT_ARGS+=(--use-c-backend --c-model-path "${MODEL_PATH}")
fi

start_process \
    "FRTApp" \
    "${FSS_ROOT}/frt_app/py_ai_core" \
    "${LOG_DIR}/frt_app.log" \
    "${FRT_PY}" "${FRT_ARGS[@]}"

wait_for_dbus_name "vn.edu.uit.FSS.FRTApp" 20 \
    || die_with_log "${LOG_DIR}/frt_app.log" \
        "FRTApp did not register D-Bus name."

start_process \
    "VideoSHMWriter" \
    "${FSS_ROOT}" \
    "${LOG_DIR}/video_writer.log" \
    "${FRT_PY}" "${FSS_ROOT}/tools/frt_video_shm_writer.py" \
        "${VIDEO_PATH}" --fps "${FPS}" --start-delay "${START_DELAY}" \
        --max-seconds "${VIDEO_SECONDS}"

sleep "${OPEN_DELAY}"
log "Emitting DOOR_OPEN"
"${DB_PY}" "${FSS_ROOT}/tools/mock_sensor_door.py" open \
    >"${LOG_DIR}/door_open.log" 2>&1

WRITER_PID="${PIDS[-1]}"
log "Waiting for video writer pid=${WRITER_PID}"
log "This waits for the video to finish. Use --video-seconds N to shorten the demo."
wait "${WRITER_PID}"
log "Video writer finished"

log "Emitting DOOR_CLOSE"
"${DB_PY}" "${FSS_ROOT}/tools/mock_sensor_door.py" close \
    >"${LOG_DIR}/door_close.log" 2>&1

log "Settling for ${SETTLE_AFTER_CLOSE}s so DB/UI can receive updates"
sleep "${SETTLE_AFTER_CLOSE}"

log "Demo complete"
