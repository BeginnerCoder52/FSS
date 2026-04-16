"""
FSS_ArchitectureDiagram_Q1.py
Generates the Q1-standard software architecture diagram for the
Fridge Supervisor System (FSS).

Run:
    python3 docs/FSS_ArchitectureDiagram_Q1.py
Output:
    docs/FSS_ArchitectureDiagram_Q1_v1.0.0.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

# ── colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":        "#F4F6F9",
    "l1_bg":     "#D6EAF8",   # hardware
    "l2_bg":     "#D5F5E3",   # middleware
    "l3_bg":     "#FDEBD0",   # application
    "proc_c":    "#2471A3",   # C/C++ process
    "proc_py":   "#1E8449",   # Python process
    "proc_js":   "#B7950B",   # Node.js process
    "proc_ai":   "#7D3C98",   # AI process
    "hw_box":    "#5D6D7E",   # hardware component
    "ipc_box":   "#117A65",   # IPC kernel
    "arrow":     "#2C3E50",
    "layer_txt": "#1A252F",
    "white":     "#FFFFFF",
    "caption":   "#212121",
}

FIG_W, FIG_H = 22, 14
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(C["bg"])
ax.set_facecolor(C["bg"])
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")

# ── helpers ───────────────────────────────────────────────────────────────────

def layer(ax, y_bot, y_top, color, label, label_color="#1A252F"):
    """Draw a horizontal layer band."""
    ax.add_patch(FancyBboxPatch(
        (0.2, y_bot), FIG_W - 0.4, y_top - y_bot,
        boxstyle="round,pad=0.05", linewidth=1.5,
        edgecolor="#AAB7B8", facecolor=color, zorder=1, alpha=0.55))
    ax.text(0.55, (y_bot + y_top) / 2, label,
            fontsize=10, fontweight="bold", color=label_color,
            va="center", ha="left", rotation=90, zorder=5)


def proc_box(ax, x, y, w, h, title, subtitle, lang_color,
             is_ai=False, zorder=4):
    """Draw a process boundary box (UML Component style)."""
    # shadow
    ax.add_patch(FancyBboxPatch(
        (x + 0.06, y - 0.06), w, h,
        boxstyle="round,pad=0.08", linewidth=0,
        facecolor="#BDC3C7", zorder=zorder - 1, alpha=0.5))
    # main box
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.08", linewidth=2,
        edgecolor=lang_color, facecolor=C["white"], zorder=zorder))
    # header bar
    ax.add_patch(FancyBboxPatch(
        (x, y + h - 0.55), w, 0.55,
        boxstyle="square,pad=0.0", linewidth=0,
        facecolor=lang_color, zorder=zorder + 1))
    ax.text(x + w / 2, y + h - 0.275, title,
            fontsize=8.5, fontweight="bold", color=C["white"],
            va="center", ha="center", zorder=zorder + 2)
    ax.text(x + w / 2, y + h / 2 - 0.18, subtitle,
            fontsize=7.5, color="#2C3E50",
            va="center", ha="center", zorder=zorder + 2,
            multialignment="center")
    # AI badge
    if is_ai:
        ax.add_patch(mpatches.RegularPolygon(
            (x + w - 0.28, y + 0.28), numVertices=6,
            radius=0.22, orientation=0,
            edgecolor=C["proc_ai"], facecolor="#E8DAEF",
            linewidth=1.5, zorder=zorder + 3))
        ax.text(x + w - 0.28, y + 0.28, "AI",
                fontsize=6, fontweight="bold", color=C["proc_ai"],
                va="center", ha="center", zorder=zorder + 4)
    # UML component notch (top-right corner)
    notch_x, notch_y = x + w - 0.22, y + h - 0.03
    ax.add_patch(FancyBboxPatch(
        (notch_x - 0.16, notch_y - 0.22), 0.32, 0.18,
        boxstyle="square,pad=0.0", linewidth=1,
        edgecolor=lang_color, facecolor=C["white"], zorder=zorder + 3))
    for dy in (0.0, 0.09):
        ax.plot([notch_x - 0.28, notch_x - 0.16],
                [notch_y - 0.13 - dy, notch_y - 0.13 - dy],
                color=lang_color, lw=1, zorder=zorder + 4)


def hw_box(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.06", linewidth=1.5,
        edgecolor=C["hw_box"], facecolor="#D5D8DC", zorder=4))
    ax.text(x + w / 2, y + h / 2, label,
            fontsize=7.5, fontweight="bold", color=C["hw_box"],
            va="center", ha="center", zorder=5, multialignment="center")


def ipc_box(ax, x, y, w, h, label):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.06", linewidth=1.8,
        edgecolor=C["ipc_box"], facecolor="#A9DFBF",
        linestyle="dashed", zorder=4))
    ax.text(x + w / 2, y + h / 2, label,
            fontsize=7.5, fontweight="bold", color=C["ipc_box"],
            va="center", ha="center", zorder=5, multialignment="center")


def arrow(ax, x1, y1, x2, y2, label, color=C["arrow"],
          lw=1.4, style="->", labelside="top", fontsize=6.8):
    """Draw an annotated arrow between two points."""
    ax.annotate("",
                xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(
                    arrowstyle=style, color=color,
                    lw=lw, connectionstyle="arc3,rad=0.0"),
                zorder=8)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    offset = 0.18 if labelside == "top" else -0.18
    if abs(x2 - x1) < 0.2:   # vertical arrow → label to the right
        ax.text(mx + 0.22, my, label,
                fontsize=fontsize, color=color,
                va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.2",
                          fc=C["bg"], ec="none", alpha=0.85),
                zorder=9)
    else:
        ax.text(mx, my + offset, label,
                fontsize=fontsize, color=color,
                va="bottom" if labelside == "top" else "top",
                ha="center",
                bbox=dict(boxstyle="round,pad=0.2",
                          fc=C["bg"], ec="none", alpha=0.85),
                zorder=9)


def bidir_arrow(ax, x1, y1, x2, y2, label, color=C["arrow"]):
    arrow(ax, x1, y1, x2, y2, label, color=color, style="<->")


# ── layer bands ───────────────────────────────────────────────────────────────
layer(ax, 0.5,  3.2,  C["l1_bg"], "L1  Hardware Layer")
layer(ax, 3.2,  6.3,  C["l2_bg"], "L2  Middleware / HAL Layer")
layer(ax, 6.3, 13.2,  C["l3_bg"], "L3  Application Logic Layer")

# layer labels (right side)
for txt, yc in [("L1: Hardware", 1.85), ("L2: Middleware / HAL", 4.75),
                ("L3: Application Logic", 9.75)]:
    ax.text(FIG_W - 0.35, yc, txt,
            fontsize=9, fontweight="bold", color=C["layer_txt"],
            va="center", ha="right", rotation=270, zorder=6)

# ── L1 – Hardware components ──────────────────────────────────────────────────
hw_box(ax,  1.2, 0.85, 2.2, 1.8, "SHT3x\n(Temp / Humidity)\nI²C Sensor")
hw_box(ax,  4.2, 0.85, 2.2, 1.8, "VL53L0X\n(Distance ToF)\nI²C Sensor")
hw_box(ax,  7.2, 0.85, 2.2, 1.8, "MC-38\n(Door Magnetic)\nGPIO Sensor")
hw_box(ax, 10.5, 0.85, 2.5, 1.8, "USB Camera\n(V4L2 Device)\n/dev/video0")
hw_box(ax, 14.5, 0.85, 2.5, 1.8, "HDMI Display\n(Electron /\nMagicMirror)")

# ── L2 – HAL Drivers (left cluster) ──────────────────────────────────────────
ax.add_patch(FancyBboxPatch(
    (1.0, 3.4), 9.5, 2.6,
    boxstyle="round,pad=0.08", linewidth=1.5,
    edgecolor="#1E8449", facecolor="#EAFAF1", zorder=2, alpha=0.7))
ax.text(5.6, 5.75, "HAL Drivers  (drivers/)",
        fontsize=8, fontweight="bold", color="#1E8449",
        va="center", ha="center", zorder=6)

hw_box(ax, 1.3, 3.55, 2.2, 1.7, "sht3x Driver\n(I²C read)")
hw_box(ax, 4.0, 3.55, 2.2, 1.7, "vl53l0x Driver\n(I²C read)")
hw_box(ax, 6.7, 3.55, 2.2, 1.7, "mc-38 Driver\n(GPIO poll)")
hw_box(ax, 9.0, 3.55, 1.3, 1.7, "V4L2\nDriver")

# ── L2 – IPC Kernel bus ───────────────────────────────────────────────────────
ipc_box(ax, 10.9, 3.4, 6.3, 2.6,
        "Linux IPC Kernel Bus\n"
        "• D-Bus Broker  (session bus)\n"
        "• ZMQ  (TCP 5555 / 5556)\n"
        "• POSIX Shared Memory  /fss_video_frame\n"
        "• systemd  (watchdog / units)")

# ── L3 – Process boxes ────────────────────────────────────────────────────────
#  SensorDaemon
proc_box(ax, 1.0, 7.0, 3.2, 5.5,
         "SensorDaemon",
         "[Process 1 – C/C++]\n\nSensorDaemonApp\nInputProcessor\nOutputProcessor\nSdbusInterface\nSystemdWatchdog",
         C["proc_c"])

#  FRTApp C++ Camera Core
proc_box(ax, 5.0, 7.0, 3.2, 5.5,
         "FRTApp · C++ Camera Core",
         "[Process 2 – C/C++]\n\nVideoCapture\n(V4L2 API)\n\nShmWriter\n→ /fss_video_frame",
         C["proc_c"])

#  FRTApp Python AI Core
proc_box(ax, 9.0, 7.0, 3.5, 5.5,
         "FRTApp · AI Inference Core",
         "[Process 3 – Python]\n\nFrtDaemonApp\nYoloPipeline\n(ultralytics / NumPy)\nSdbusInterface",
         C["proc_py"], is_ai=True)

#  DBDaemon
proc_box(ax, 13.2, 7.0, 3.5, 5.5,
         "DBDaemon",
         "[Process 4 – Python]\n\nDbDaemonApp\nSqliteManager\nPosixShmReader\nDiskFileManager\nDbDbusInterface",
         C["proc_py"])

#  MagicMirror UI
proc_box(ax, 17.4, 7.0, 4.3, 5.5,
         "MagicMirror UI",
         "[Process 5 – Node.js + Python]\n\nMMM-FSS-Food\nMMM-FSS-Env\nnode_helper.js\n──────────\npy_bridge:\nfood_dbus_listener.py\nenv_zmq_client.py",
         C["proc_js"])

# ── arrows: L1 → L2 (hardware to drivers) ────────────────────────────────────
for hx, dx in [(2.3, 2.4), (5.3, 5.1), (8.3, 7.8)]:
    arrow(ax, hx, 2.65, dx, 3.55, "I²C\nRaw Data", color="#5D6D7E",
          lw=1.3, labelside="top", fontsize=6.5)
arrow(ax, 11.75, 2.65, 9.65, 3.55, "V4L2\nFrames", color="#5D6D7E",
      lw=1.3, labelside="top", fontsize=6.5)

# ── arrows: L2 HAL → L3 SensorDaemon ─────────────────────────────────────────
arrow(ax, 2.4, 5.25, 2.4, 7.0,
      "I²C Parsed\nData Struct", color=C["proc_c"], lw=1.4, labelside="top")
arrow(ax, 5.1, 5.25, 5.1, 7.0,
      "GPIO\nEdge Event", color=C["proc_c"], lw=1.4, labelside="top")
arrow(ax, 7.8, 5.25, 6.5, 7.0,
      "GPIO\nEdge Event", color=C["proc_c"], lw=1.4, labelside="top")

# ── V4L2 Driver → FRTApp C++ ──────────────────────────────────────────────────
arrow(ax, 9.65, 5.25, 6.6, 7.0,
      "V4L2\nRaw Frames", color=C["proc_c"], lw=1.4, labelside="top")

# ── POSIX SHM: FRTApp C++ → AI Core ─────────────────────────────────────────
arrow(ax, 8.2, 9.75, 9.0, 9.75,
      "POSIX SHM\n/fss_video_frame\n(Raw Bytes)", color=C["proc_ai"],
      lw=1.6, labelside="top")

# ── D-Bus: AI Core → DBDaemon ────────────────────────────────────────────────
arrow(ax, 12.5, 10.5, 13.2, 10.5,
      "D-Bus Signal\nFoodDetected\n{items, frame_id}", color=C["ipc_box"],
      lw=1.6, labelside="top")

# ── ZMQ: SensorDaemon → DBDaemon ─────────────────────────────────────────────
ax.annotate("",
            xy=(13.2, 9.0), xytext=(4.2, 9.0),
            arrowprops=dict(arrowstyle="->", color="#E67E22",
                            lw=1.5,
                            connectionstyle="arc3,rad=-0.25"),
            zorder=8)
ax.text(8.8, 7.55, "ZMQ IPC · tcp://127.0.0.1:5555\nEnvDataUpdated  {temp, hum, dist, door}",
        fontsize=6.8, color="#E67E22", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", fc=C["bg"],
                  ec="#E67E22", alpha=0.9), zorder=9)

# ── ZMQ: SensorDaemon → MMM-Env py_bridge ────────────────────────────────────
ax.annotate("",
            xy=(17.4, 8.5), xytext=(4.2, 8.5),
            arrowprops=dict(arrowstyle="->", color="#E67E22",
                            lw=1.3, linestyle="dashed",
                            connectionstyle="arc3,rad=0.22"),
            zorder=8)
ax.text(11.5, 13.0, "ZMQ IPC · tcp://127.0.0.1:5556\nEnvDataUpdated  (broadcast)",
        fontsize=6.8, color="#E67E22", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.25", fc=C["bg"],
                  ec="#E67E22", alpha=0.9), zorder=9)

# ── D-Bus: DBDaemon → MMM-Food py_bridge ─────────────────────────────────────
arrow(ax, 16.7, 10.2, 17.4, 10.2,
      "D-Bus Signal\nUIUpdateRequired\n{food_list, snapshot}", color=C["ipc_box"],
      lw=1.5, labelside="top")

# ── Python-shell stdout: py_bridge → node_helper ─────────────────────────────
ax.text(19.6, 8.1,
        "python-shell\nstdout JSON\n──────────\nnode_helper.js\n↕ socket.io\nMMM-FSS-*.js",
        fontsize=6.8, color=C["proc_js"], ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.28", fc="#FFFDE7",
                  ec=C["proc_js"], lw=1.2, alpha=0.95),
        zorder=9)

# ── Systemd watchdog (L2 IPC box → daemons) ──────────────────────────────────
ax.annotate("",
            xy=(2.6, 12.5), xytext=(13.0, 5.8),
            arrowprops=dict(arrowstyle="<->", color="#884EA0",
                            lw=1.2, linestyle="dotted",
                            connectionstyle="arc3,rad=-0.12"),
            zorder=7)
ax.text(7.0, 11.5, "systemd watchdog\n(READY=1 / WATCHDOG=1)",
        fontsize=6.5, color="#884EA0", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.22", fc=C["bg"],
                  ec="#884EA0", alpha=0.85),
        zorder=9)

# ── legend ────────────────────────────────────────────────────────────────────
legend_x, legend_y = 0.85, 12.6
ax.add_patch(FancyBboxPatch(
    (legend_x - 0.15, legend_y - 2.4), 4.4, 2.6,
    boxstyle="round,pad=0.1", linewidth=1.2,
    edgecolor="#AAB7B8", facecolor=C["white"], zorder=10, alpha=0.92))
ax.text(legend_x + 2.0, legend_y + 0.05, "Legend",
        fontsize=9, fontweight="bold", color=C["layer_txt"],
        ha="center", zorder=11)

legend_items = [
    (C["proc_c"],   "Process  [C/C++]"),
    (C["proc_py"],  "Process  [Python]"),
    (C["proc_js"],  "Process  [Node.js]"),
    (C["proc_ai"],  "AI Inference Component  ⬡"),
    (C["hw_box"],   "Hardware / Device"),
    (C["ipc_box"],  "IPC Kernel Bus  (dashed)"),
    ("#E67E22",     "ZMQ IPC Channel"),
    ("#884EA0",     "systemd  (dashed/dotted)"),
]
for i, (color, label) in enumerate(legend_items):
    yi = legend_y - 0.32 * (i + 1)
    ax.add_patch(mpatches.Rectangle(
        (legend_x, yi - 0.10), 0.35, 0.20,
        color=color, zorder=11))
    ax.text(legend_x + 0.48, yi, label,
            fontsize=7.2, color=C["layer_txt"], va="center", zorder=11)

# ── title & caption ───────────────────────────────────────────────────────────
ax.text(FIG_W / 2, 13.55,
        "FSS – Software Architecture Diagram (Component / C4 Context View)",
        fontsize=13, fontweight="bold", color=C["layer_txt"],
        ha="center", va="center", zorder=12)

ax.text(FIG_W / 2, 0.22,
        "Hình 1: Kiến trúc phần mềm hệ thống Fridge Supervisor System (FSS) – "
        "Phân tầng ba lớp (L1/L2/L3), ranh giới tiến trình, giao thức IPC và thành phần AI",
        fontsize=8.5, color=C["caption"], ha="center", va="center",
        style="italic", zorder=12)

# ── save ──────────────────────────────────────────────────────────────────────
import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "FSS_ArchitectureDiagram_Q1_v1.0.0.png")
fig.savefig(out, dpi=180, bbox_inches="tight",
            facecolor=C["bg"], edgecolor="none")
print(f"Saved: {out}")
