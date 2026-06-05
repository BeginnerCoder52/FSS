const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../js/session_logger");
const { resolvePythonExecutable } = require("../fss_paths");

module.exports = NodeHelper.create({
    start() {
        SessionLog.info("[MMM-FSS-LivePreview] Node helper started");
        this.pythonProcess = null;
        this.started = false;
    },
    socketNotificationReceived(notification) {
        if (notification === "LIVE_PREVIEW_START" && !this.started) {
            this.startBridge();
        }
    },
    startBridge() {
        const script = path.join(__dirname, "py_bridge", "live_preview_bridge.py");

        if (!fs.existsSync(script)) {
            console.error(`[MMM-FSS-LivePreview] Script not found: ${script}`);
            this.sendSocketNotification("LIVE_PREVIEW_ERROR", { error: `Script not found: ${script}` });
            return;
        }

        const pythonExec = resolvePythonExecutable(__dirname);
        this.pythonProcess = spawn(pythonExec, [script]);

        let buffer = "";
        this.pythonProcess.stdout.on("data", (data) => {
            buffer += data.toString();
            const lines = buffer.split("\n");
            buffer = lines.pop();
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const msg = JSON.parse(line);
                    if (msg.type === "FRAME") {
                        this.sendSocketNotification("LIVE_PREVIEW_FRAME", { frame: msg.data });
                    } else if (msg.type === "ERROR") {
                        console.error("[MMM-FSS-LivePreview] Bridge error:", msg.message);
                        this.sendSocketNotification("LIVE_PREVIEW_ERROR", { error: msg.message });
                    }
                } catch (e) {
                    // non-JSON output
                }
            }
        });
        this.pythonProcess.stderr.on("data", (data) => {
            console.error(`[MMM-FSS-LivePreview] Python stderr: ${data.toString()}`);
        });
        this.pythonProcess.on("error", (err) => {
            console.error("[MMM-FSS-LivePreview] Failed to start bridge:", err.message);
            this.sendSocketNotification("LIVE_PREVIEW_ERROR", { error: `Bridge start failed: ${err.message}` });
            this.started = false;
            this.pythonProcess = null;
        });
        this.pythonProcess.on("close", (code) => {
            console.warn(`[MMM-FSS-LivePreview] Python bridge closed with code ${code}`);
            this.started = false;
            this.pythonProcess = null;
        });
        this.started = true;
    },
    stop() {
        SessionLog.info("[MMM-FSS-LivePreview] Node helper stopped");
        if (this.pythonProcess) {
            this.pythonProcess.kill("SIGTERM");
        }
        this.pythonProcess = null;
    }
});
