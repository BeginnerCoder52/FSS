const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const SessionLog = require("../../../js/session_logger");

module.exports = NodeHelper.create({
    start() {
        SessionLog.info("[MMM-FSS-Recommend] Node helper started");
        this.pythonProcess = null;
        this.started = false;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "RECIPE_SEARCH" && !this.started) {
            this.startBridge();
        }
        if (notification === "RECIPE_SEARCH" && this.pythonProcess) {
            this.pythonProcess.stdin.write(JSON.stringify({
                type: "SEARCH",
                recipe: payload.recipe
            }) + "\n");
        }
    },
    startBridge() {
        const script = require("path").join(__dirname, "py_bridge", "recommend_dbus_listener.py");
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
                    if (msg.type === "RESULT") {
                        this.sendSocketNotification("RECOMMEND_RESULT", msg.data);
                    } else if (msg.type === "ERROR") {
                        console.error("[MMM-FSS-Recommend] Error:", msg.message);
                    }
                } catch(e) {}
            }
        });
        this.pythonProcess.on("error", (err) => {
            console.error("[MMM-FSS-Recommend] Failed to start bridge:", err);
        });
        this.started = true;
    },
    stop() {
        if (this.pythonProcess) this.pythonProcess.kill();
    }
});
