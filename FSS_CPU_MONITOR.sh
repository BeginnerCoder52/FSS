#!/usr/bin/env bash
# ==============================================================================
# FSS_CPU_MONITOR.sh — FSS System Resource Usage Monitor
#
# Captures live CPU and RAM usage for ALL FSS daemons while the system runs.
# Designed to populate thesis section 4.4.2:
#   "Phân tích tải tài nguyên hệ thống (Memory & CPU Footprint) trên Raspberry Pi"
#
# Features:
#   - Live per-daemon table (CPU%, MEM%, RSS, VSZ) updated every 2s
#   - Background CSV logging for post-analysis
#   - Automatic daemon discovery (finds by executable name)
#   - Summary report on exit (min/max/avg per daemon)
#   - Optional gnuplot chart generation
#
# Usage:
#   bash FSS_CPU_MONITOR.sh                           # default: 2s interval
#   bash FSS_CPU_MONITOR.sh --interval 5              # 5-second sampling
#   bash FSS_CPU_MONITOR.sh --duration 120            # auto-stop after 120s
#   bash FSS_CPU_MONITOR.sh --output /tmp/my_stats    # custom output dir
#   bash FSS_CPU_MONITOR.sh --chart                   # generate gnuplot chart
#   bash FSS_CPU_MONITOR.sh --no-live                 # background only (no display)
#   bash FSS_CPU_MONITOR.sh --help                    # show help
#
# Output (in OUTPUT_DIR/):
#   fss_resource_usage.csv     — Full time-series data
#   fss_summary_report.txt     — Min/Max/Avg per daemon
#   fss_resource_chart.png     — (--chart) gnuplot visualization
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/fss_profile.conf" 2>/dev/null || true

# ==============================================================================
# Configuration
# ==============================================================================

INTERVAL=2
DURATION=0              # 0 = run until Ctrl+C
OUTPUT_DIR="${FSS_LOG_DIR:-/var/log/fss}/resource_monitor"
GENERATE_CHART=false
LIVE_DISPLAY=true

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CSV_FILE=""
SUMMARY_FILE=""
CHART_FILE=""

# All known FSS daemon patterns (executable names or python script names)
FSS_PATTERNS=(
    "sensor_daemon_exec"
    "camera_core_exec"
    "db_daemon/src/main.py"
    "frt_ai/src/main.py"
    "recipe_extractor_main.py"
    "recommend_daemon/src/main.py"
)

FSS_LABELS=(
    "SensorDaemon"
    "CameraCore"
    "DBDaemon"
    "FRT_AI"
    "RecipeExtractor"
    "RecommendDaemon"
)

# ==============================================================================
# Help
# ==============================================================================

usage() {
    echo "Usage: bash FSS_CPU_MONITOR.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --interval N    Sampling interval in seconds (default: 2)"
    echo "  --duration N    Auto-stop after N seconds (default: run until Ctrl+C)"
    echo "  --output DIR    Output directory (default: /var/log/fss/resource_monitor)"
    echo "  --chart         Generate gnuplot chart (requires gnuplot)"
    echo "  --no-live       Run in silent logging mode (no terminal table)"
    echo "  --help          Show this help"
    exit 0
}

# ==============================================================================
# Parse arguments
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --interval) INTERVAL="$2"; shift 2 ;;
        --duration) DURATION="$2"; shift 2 ;;
        --output)   OUTPUT_DIR="$2"; shift 2 ;;
        --chart)    GENERATE_CHART=true; shift ;;
        --no-live)  LIVE_DISPLAY=false; shift ;;
        --help|-h)  usage ;;
        *)          echo "Unknown: $1"; usage ;;
    esac
done

# ==============================================================================
# Setup
# ==============================================================================

mkdir -p "$OUTPUT_DIR"
CSV_FILE="${OUTPUT_DIR}/fss_resource_usage_${TIMESTAMP}.csv"
SUMMARY_FILE="${OUTPUT_DIR}/fss_summary_report_${TIMESTAMP}.txt"
CHART_FILE="${OUTPUT_DIR}/fss_resource_chart_${TIMESTAMP}.png"

# Write CSV header
echo "timestamp,elapsed_sec,daemon,pid,cpu_pct,mem_pct,rss_kb,vsz_kb" > "$CSV_FILE"

# Store all samples for summary
declare -A ALL_SAMPLES
for label in "${FSS_LABELS[@]}"; do
    ALL_SAMPLES["${label}_cpu"]=""
    ALL_SAMPLES["${label}_mem"]=""
    ALL_SAMPLES["${label}_rss"]=""
done

GLOBAL_CPU=""
GLOBAL_MEM=""
GLOBAL_SAMPLES=0
GLOBAL_CPU_SAMPLES=""

START_TIME=$(date +%s)

# ==============================================================================
# Functions
# ==============================================================================

find_daemon_pids() {
    local pattern="$1"
    # Try exact process name match first, then fallback to command line
    pgrep -f "$pattern" 2>/dev/null || true
}

get_proc_stats() {
    local pid="$1"
    if [[ ! -d "/proc/$pid" ]]; then
        echo "0,0,0,0"
        return
    fi

    local stat_file="/proc/$pid/stat"
    local status_file="/proc/$pid/status"

    if [[ ! -f "$stat_file" || ! -f "$status_file" ]]; then
        echo "0,0,0,0"
        return
    fi

    # CPU% = (utime + stime) delta / total time delta * 100
    # We use /proc/stat for total CPU time
    # For simplicity, get cpu_clk_tck and compute
    # Actually, simpler: use 'ps' for CPU% since it's one-shot
    local ps_out
    ps_out=$(ps -p "$pid" -o %cpu=,%mem=,rss=,vsz= 2>/dev/null || echo "0 0 0 0")
    echo "$ps_out"
}

sample_global() {
    local meminfo
    meminfo=$(free -m 2>/dev/null || echo "")
    local mem_total mem_used cpu_idle
    mem_total=$(echo "$meminfo" | awk '/Mem:/{print $2}')
    mem_used=$(echo "$meminfo" | awk '/Mem:/{print $3}')
    cpu_idle=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $8}' || echo "0")
    local cpu_used
    cpu_used=$(echo "100 - $cpu_idle" | bc 2>/dev/null || echo "0")
    echo "$cpu_used $mem_used $mem_total"
}

sample_all() {
    local now
    now=$(date '+%Y-%m-%d %H:%M:%S')
    local elapsed=$(( $(date +%s) - START_TIME ))
    local row

    # Sample global
    local global_stats
    global_stats=$(sample_global)
    GLOBAL_CPU=$(echo "$global_stats" | awk '{print $1}')
    GLOBAL_MEM=$(echo "$global_stats" | awk '{print $2 "M / " $3 "M"}')
    GLOBAL_SAMPLES=$((GLOBAL_SAMPLES + 1))

    # Sample each daemon
    for i in "${!FSS_PATTERNS[@]}"; do
        local pattern="${FSS_PATTERNS[$i]}"
        local label="${FSS_LABELS[$i]}"
        local pids
        pids=$(find_daemon_pids "$pattern")
        local cpu_total=0
        local mem_total=0
        local rss_total=0
        local vsz_total=0
        local pid_list=""

        if [[ -n "$pids" ]]; then
            while IFS= read -r pid; do
                [[ -z "$pid" ]] && continue
                local stats
                stats=$(get_proc_stats "$pid")
                local cpu=$(echo "$stats" | awk '{print $1}')
                local mem=$(echo "$stats" | awk '{print $2}')
                local rss=$(echo "$stats" | awk '{print $3}')
                local vsz=$(echo "$stats" | awk '{print $4}')
                cpu_total=$(echo "$cpu_total + $cpu" | bc 2>/dev/null || echo "$cpu_total")
                mem_total=$(echo "$mem_total + $mem" | bc 2>/dev/null || echo "$mem_total")
                rss_total=$((rss_total + rss))
                vsz_total=$((vsz_total + vsz))
                pid_list="${pid_list}${pid},"
            done <<< "$pids"
            pid_list="${pid_list%,}"
        fi

        # Fallback: if CPU is 0 but process exists, 'ps' may have returned w/o values
        # Just use whatever we got

        # Record sample
        row="${now},${elapsed},${label},${pid_list:-0},${cpu_total},${mem_total},${rss_total},${vsz_total}"
        echo "$row" >> "$CSV_FILE"

        # Accumulate for summary
        ALL_SAMPLES["${label}_cpu"]="${ALL_SAMPLES[${label}_cpu]}${cpu_total},"
        ALL_SAMPLES["${label}_mem"]="${ALL_SAMPLES[${label}_mem]}${mem_total},"
        ALL_SAMPLES["${label}_rss"]="${ALL_SAMPLES[${label}_rss]}${rss_total},"
    done

    GLOBAL_CPU_SAMPLES="${GLOBAL_CPU_SAMPLES}${GLOBAL_CPU},"
}

print_table_header() {
    printf "%-18s %-7s %-8s %-8s %-10s %-10s\n" \
        "DAEMON" "PID" "CPU%" "MEM%" "RSS(KB)" "VSZ(KB)"
    printf -- "------------------------------------------------------------------------------\n"
}

print_table_row() {
    local label="$1"
    local pid="$2"
    local cpu="$3"
    local mem="$4"
    local rss="$5"
    local vsz="$6"
    printf "%-18s %-7s %-8.1f %-8.1f %-10s %-10s\n" \
        "$label" "$pid" "$cpu" "$mem" "$rss" "$vsz"
}

compute_stats() {
    local values="$1"
    # values is comma-separated list of numbers
    local min_val=""
    local max_val=""
    local sum=0
    local count=0
    local avg_val=""

    IFS=',' read -ra arr <<< "$values"
    for val in "${arr[@]}"; do
        val=$(echo "$val" | tr -d ' ')
        [[ -z "$val" ]] && continue
        if [[ -z "$min_val" ]] || (( $(echo "$val < $min_val" | bc -l 2>/dev/null || echo 1) )); then
            min_val=$val
        fi
        if [[ -z "$max_val" ]] || (( $(echo "$val > $max_val" | bc -l 2>/dev/null || echo 1) )); then
            max_val=$val
        fi
        sum=$(echo "$sum + $val" | bc -l 2>/dev/null || echo "$sum")
        count=$((count + 1))
    done

    if [[ $count -gt 0 ]]; then
        avg_val=$(echo "scale=2; $sum / $count" | bc -l 2>/dev/null || echo "0")
    fi

    echo "${min_val:-0}|${max_val:-0}|${avg_val:-0}|${count}"
}

generate_summary() {
    local elapsed_total=$(( $(date +%s) - START_TIME ))

    cat > "$SUMMARY_FILE" << EOF
===============================================================================
FSS System Resource Usage Summary
Generated: $(date)
Sampling interval: ${INTERVAL}s
Total duration: ${elapsed_total}s
Samples collected: ${GLOBAL_SAMPLES}
Output CSV: ${CSV_FILE}
===============================================================================

--- GLOBAL SYSTEM ---
Global CPU samples: ${GLOBAL_CPU_SAMPLES%,}

--- PER-DAEMON STATISTICS ---

$(printf "%-20s %-12s %-12s %-12s %-12s\n" "Daemon" "Metric" "Min" "Max" "Avg")
$(printf -- "--------------------------------------------------------------------------------\n")

EOF

    for i in "${!FSS_LABELS[@]}"; do
        local label="${FSS_LABELS[$i]}"
        local cpu_data="${ALL_SAMPLES[${label}_cpu]}"
        local mem_data="${ALL_SAMPLES[${label}_mem]}"
        local rss_data="${ALL_SAMPLES[${label}_rss]}"

        local cpu_stats
        cpu_stats=$(compute_stats "$cpu_data")
        local cpu_min cpu_max cpu_avg cpu_cnt
        IFS='|' read -r cpu_min cpu_max cpu_avg cpu_cnt <<< "$cpu_stats"

        local mem_stats
        mem_stats=$(compute_stats "$mem_data")
        local mem_min mem_max mem_avg mem_cnt
        IFS='|' read -r mem_min mem_max mem_avg mem_cnt <<< "$mem_stats"

        local rss_stats
        rss_stats=$(compute_stats "$rss_data")
        local rss_min rss_max rss_avg rss_cnt
        IFS='|' read -r rss_min rss_max rss_avg rss_cnt <<< "$rss_stats"

        cat >> "$SUMMARY_FILE" << EOF
${label}
  CPU%:      min=${cpu_min}%  max=${cpu_max}%  avg=${cpu_avg}%  (${cpu_cnt} samples)
  MEM%:      min=${mem_min}%  max=${mem_max}%  avg=${mem_avg}%  (${mem_cnt} samples)
  RSS (KB):  min=${rss_min}  max=${rss_max}  avg=${rss_avg}  (${rss_cnt} samples)

EOF
    done

    cat >> "$SUMMARY_FILE" << EOF
===============================================================================
EOF

    fss_log_ok "Summary saved to ${SUMMARY_FILE}"
}

generate_chart() {
    if ! command -v gnuplot &>/dev/null; then
        fss_log_warn "gnuplot not found, skipping chart generation"
        return
    fi

    fss_log_info "Generating resource chart..."

    cat > /tmp/fss_plot.gnuplot << 'GNUEOF'
set terminal pngcairo size 1600,900 enhanced font 'DejaVu Sans,10'
set output 'CHART_FILE_PLACEHOLDER'
set title 'FSS System Resource Usage Over Time' font 'DejaVu Sans,14'
set xlabel 'Elapsed Time (seconds)'
set ylabel 'Usage'
set grid
set key outside right
set datafile separator ','

# CPU subplot
set multiplot layout 2,1 title 'FSS Daemon Resource Footprint' font 'DejaVu Sans,16'

set ylabel 'CPU (%)'
set yrange [0:*]
plot 'CSV_FILE_PLACEHOLDER' using (column(2)):5 every ::1 title 'SensorDaemon' with lines linewidth 2, \
     '' using (column(2)):5 every ::2 title 'CameraCore' with lines linewidth 2, \
     '' using (column(2)):5 every ::3 title 'DBDaemon' with lines linewidth 2, \
     '' using (column(2)):5 every ::4 title 'FRT_AI' with lines linewidth 2, \
     '' using (column(2)):5 every ::5 title 'RecipeExtractor' with lines linewidth 2, \
     '' using (column(2)):5 every ::6 title 'RecommendDaemon' with lines linewidth 2

set ylabel 'RSS (KB)'
set yrange [0:*]
plot 'CSV_FILE_PLACEHOLDER' using (column(2)):7 every ::1 title 'SensorDaemon' with lines linewidth 2, \
     '' using (column(2)):7 every ::2 title 'CameraCore' with lines linewidth 2, \
     '' using (column(2)):7 every ::3 title 'DBDaemon' with lines linewidth 2, \
     '' using (column(2)):7 every ::4 title 'FRT_AI' with lines linewidth 2, \
     '' using (column(2)):7 every ::5 title 'RecipeExtractor' with lines linewidth 2, \
     '' using (column(2)):7 every ::6 title 'RecommendDaemon' with lines linewidth 2

unset multiplot
GNUEOF

    # Replace placeholders
    sed -i "s|CSV_FILE_PLACEHOLDER|${CSV_FILE}|g; s|CHART_FILE_PLACEHOLDER|${CHART_FILE}|g" /tmp/fss_plot.gnuplot

    if gnuplot /tmp/fss_plot.gnuplot 2>/dev/null; then
        fss_log_ok "Chart saved to ${CHART_FILE}"
    else
        fss_log_warn "gnuplot chart generation failed (CSV has data)"
    fi

    rm -f /tmp/fss_plot.gnuplot
}

# ==============================================================================
# Signal handler
# ==============================================================================

cleanup() {
    echo ""
    fss_log_info "Stopping resource monitor..."

    # Generate summary
    generate_summary

    # Generate chart if requested
    if [[ "$GENERATE_CHART" == true ]]; then
        generate_chart
    fi

    # Print summary to terminal
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  FSS Resource Usage Summary                                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Duration: $(( $(date +%s) - START_TIME ))s  |  Samples: ${GLOBAL_SAMPLES}"
    echo "  CSV data: ${CSV_FILE}"
    echo "  Report:   ${SUMMARY_FILE}"
    echo ""
    echo "  Quick stats (avg CPU% / avg RSS):"
    for i in "${!FSS_LABELS[@]}"; do
        local label="${FSS_LABELS[$i]}"
        local cpu_data="${ALL_SAMPLES[${label}_cpu]}"
        local rss_data="${ALL_SAMPLES[${label}_rss]}"

        local cpu_stats
        cpu_stats=$(compute_stats "$cpu_data")
        local cpu_avg
        cpu_avg=$(echo "$cpu_stats" | cut -d'|' -f3)

        local rss_stats
        rss_stats=$(compute_stats "$rss_data")
        local rss_avg
        rss_avg=$(echo "$rss_stats" | cut -d'|' -f3)

        printf "  %-18s  CPU avg: %6s%%  RSS avg: %8s KB\n" "$label" "$cpu_avg" "$rss_avg"
    done
    echo ""
    echo "  Full report: cat ${SUMMARY_FILE}"
    echo ""

    exit 0
}

trap cleanup SIGTERM SIGINT

# ==============================================================================
# Main monitoring loop
# ==============================================================================

fss_log_info "FSS Resource Monitor started"
fss_log_info "  Interval: ${INTERVAL}s | Duration: ${DURATION}s (0=unlimited)"
fss_log_info "  Output:   ${OUTPUT_DIR}"
fss_log_info "  CSV:      ${CSV_FILE}"
fss_log_info ""
fss_log_info "Run FSS daemons in another terminal with: bash FSS_RUN.sh"
fss_log_info "Press Ctrl+C to stop monitoring and generate summary."
echo ""

# Initial sample to set baseline
sleep 0.5

# Show table header once
if [[ "$LIVE_DISPLAY" == true ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║  FSS Resource Monitor — Live (refreshing every ${INTERVAL}s)        ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
fi

LOOP_COUNT=0
MAX_LOOPS=0
[[ "$DURATION" -gt 0 ]] && MAX_LOOPS=$(( DURATION / INTERVAL ))

while true; do
    # Check duration limit
    if [[ "$MAX_LOOPS" -gt 0 && "$LOOP_COUNT" -ge "$MAX_LOOPS" ]]; then
        fss_log_info "Duration limit reached (${DURATION}s)"
        break
    fi

    sample_all

    if [[ "$LIVE_DISPLAY" == true ]]; then
        # Clear previous table (move cursor up)
        if [[ "$LOOP_COUNT" -gt 0 ]]; then
            # Move up: header (2) + daemon lines (6) + global (1) + blank (1) = 10 lines
            # Plus elapsed header
            printf "\033[%dA" 11
        fi

        local elapsed=$(( $(date +%s) - START_TIME ))
        echo "  Elapsed: ${elapsed}s | Interval: ${INTERVAL}s | Samples: $((LOOP_COUNT + 1))"
        print_table_header

        for i in "${!FSS_PATTERNS[@]}"; do
            local pattern="${FSS_PATTERNS[$i]}"
            local label="${FSS_LABELS[$i]}"
            local pids
            pids=$(find_daemon_pids "$pattern")
            local pid_display="0"
            local cpu_val=0
            local mem_val=0
            local rss_val=0
            local vsz_val=0

            if [[ -n "$pids" ]]; then
                # Get the latest from CSV (last line for this daemon)
                local line
                line=$(grep ",${label}," "$CSV_FILE" | tail -1 2>/dev/null || echo "")
                if [[ -n "$line" ]]; then
                    pid_display=$(echo "$line" | cut -d',' -f4)
                    cpu_val=$(echo "$line" | cut -d',' -f5)
                    mem_val=$(echo "$line" | cut -d',' -f6)
                    rss_val=$(echo "$line" | cut -d',' -f7)
                    vsz_val=$(echo "$line" | cut -d',' -f8)
                fi
            fi

            print_table_row "$label" "$pid_display" "$cpu_val" "$mem_val" "$rss_val" "$vsz_val"
        done

        echo -n "  [GLOBAL] CPU: ${GLOBAL_CPU}%  "
        echo "$GLOBAL_MEM"
    fi

    LOOP_COUNT=$((LOOP_COUNT + 1))
    sleep "$INTERVAL"
done

cleanup
