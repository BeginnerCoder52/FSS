const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const SessionLog = require("../../../js/session_logger");

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
        const script = require("path").join(__dirname, "py_bridge", "live_preview_bridge.py");
        this.pythonProcess = spawn("/usr/bin/python3", [script]);

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
                    }
                } catch(e) {}
            }
        });
        this.started = true;
    },
    stop() {
        if (this.pythonProcess) this.pythonProcess.kill();
    }
});
