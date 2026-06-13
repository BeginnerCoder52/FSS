#!/usr/bin/env bash
# FSS Resource Monitor - Gnuplot Chart Generator
# Usage: bash tools/plot_resource_usage.sh [csv_file]
set -euo pipefail

CSV="${1:-/var/log/fss/resource_monitor/fss_resource_usage_20260608_015545.csv}"
OUTDIR="$(dirname "$CSV")"
BASE="$(basename "$CSV" .csv)"
TMPDIR="/tmp/fss_plots_$$"
mkdir -p "$TMPDIR"

echo "==> Pre-processing: extracting per-daemon clean data..."
# Fields: ts, elapsed, daemon, pid..., cpu, mem, rss, vsz
# Last 4 are always cpu, mem, rss, vsz regardless of # of PIDs
awk -F',' '
NR == 1 { next }
{
  nf   = NF
  vsz  = $(nf)
  rss  = $(nf-1)
  mem  = $(nf-2)
  cpu  = $(nf-3)
  elap = $2
  dae  = $3
  gsub(/ /, "", dae)
  print elap, cpu, mem, rss > "'"$TMPDIR"'/" dae ".dat"
}
' "$CSV"

echo "   Daemons found:"
ls "$TMPDIR"/*.dat | sed 's/.*\///; s/\.dat//' | sort
echo

# Build gnuplot command list
DAEMONS=()
COLORS=(1 2 3 4 5 6 7)
for f in "$TMPDIR"/*.dat; do
  DAEMONS+=("$(basename "$f" .dat)")
done

# Build plot commands for each metric
build_plot_cmd() {
  local col=$1    # gnuplot column (3=cpu, 4=mem, 5=rss)
  local ylabel=$2
  local title=$3
  local fname=$4
  local opts=""
  local first=1
  local i=0
  for d in "${DAEMONS[@]}"; do
    local file="$TMPDIR/$d.dat"
    local lt=${COLORS[$i]}
    if [ "$first" -eq 1 ]; then
      opts+="plot \"$file\" using 1:$col title \"$d\" lt $lt lw 2"
      first=0
    else
      opts+=", \"\" using 1:$col title \"$d\" lt $lt lw 2"
    fi
    i=$((i+1))
  done
  echo "$opts"
}

CPU_CMD=$(build_plot_cmd 2 "CPU %" "CPU Usage" "cpu")
MEM_CMD=$(build_plot_cmd 3 "Memory %" "Memory Usage" "mem")
RSS_CMD=$(build_plot_cmd 4 "RSS (KB)" "RSS" "rss")

echo "==> Generating PNG charts with gnuplot..."

gnuplot <<GNUPLOT_EOF
set terminal pngcairo size 1400,900 enhanced font "DejaVuSans,10"
set datafile separator " "
set style data lines
set grid
set key outside right

# 1) CPU Usage
set output "$OUTDIR/${BASE}_cpu.png"
set title "FSS Daemon CPU Usage Over Time"
set xlabel "Elapsed Time (s)"
set ylabel "CPU %"
set yrange [0:]
$CPU_CMD

# 2) Memory Usage
set output "$OUTDIR/${BASE}_mem.png"
set title "FSS Daemon Memory Usage Over Time"
set xlabel "Elapsed Time (s)"
set ylabel "Memory %"
set yrange [0:]
$MEM_CMD

# 3) RSS
set output "$OUTDIR/${BASE}_rss.png"
set title "FSS Daemon RSS (Resident Set Size) Over Time"
set xlabel "Elapsed Time (s)"
set ylabel "RSS (KB)"
set format y "%.0f"
set yrange [0:]
$RSS_CMD
GNUPLOT_EOF

# 4) Multi-panel summary (stacked vertically)
gnuplot <<GNUPLOT_EOF
set terminal pngcairo size 1400,1100 enhanced font "DejaVuSans,10"
set datafile separator " "
set style data lines
set grid
set lmargin 10

set output "$OUTDIR/${BASE}_multipanel.png"
set multiplot layout 3,1 title "FSS Resource Summary  ({/*1.2 $BASE})" font ",14"

set ylabel "CPU %"
set yrange [0:]
$CPU_CMD

set ylabel "Memory %"
set yrange [0:]
$MEM_CMD

set ylabel "RSS (KB)"
set format y "%.0f"
set yrange [0:]
$RSS_CMD

unset multiplot
GNUPLOT_EOF

# Cleanup
rm -rf "$TMPDIR"

echo "==> Done! Generated:"
for png in "$OUTDIR/${BASE}"_{cpu,mem,rss,multipanel}.png; do
  if [ -f "$png" ]; then
    ls -lh "$png"
  fi
done
echo
echo "Run:  firefox $OUTDIR/${BASE}_multipanel.png"
