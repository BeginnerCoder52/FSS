const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../js/session_logger");
const { resolvePythonExecutable } = require("../fss_paths");

module.exports = NodeHelper.create({
    start() {
        SessionLog.info("[MMM-FSS-Recommend] Node helper started");
        this.pythonProcess = null;
        this.started = false;
        this.processReady = false;
        this.pendingQueue = [];
    },

    socketNotificationReceived(notification, payload) {
        if (notification === "RECIPE_SEARCH") {
            if (!this.started) {
                this.startBridge();
            }
            // Buffer write if process not yet ready (startup in progress)
            if (!this.processReady) {
                this.pendingQueue.push(payload.recipe);
                return;
            }
            this.sendSearch(payload.recipe);
        }
    },

    sendSearch(recipe) {
        if (!this.pythonProcess || this.pythonProcess.killed) {
            console.error("[MMM-FSS-Recommend] Cannot send search: process not available");
            this.sendSocketNotification("RECOMMEND_ERROR", { error: "Bridge process not available" });
            return;
        }
        this.sendSocketNotification("RECOMMEND_LOADING", {});
        this.pythonProcess.stdin.write(JSON.stringify({ type: "SEARCH", recipe }) + "\n");
    },

    startBridge() {
        const script = path.join(__dirname, "py_bridge", "recommend_dbus_listener.py");

        if (!fs.existsSync(script)) {
            console.error(`[MMM-FSS-Recommend] Python script not found: ${script}`);
            this.sendSocketNotification("RECOMMEND_ERROR", { error: `Script not found: ${script}` });
            this.started = false;
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
                    if (msg.type === "RESULT") {
                        this.sendSocketNotification("RECOMMEND_RESULT", msg.data);
                    } else if (msg.type === "ERROR") {
                        console.error("[MMM-FSS-Recommend] Error:", msg.message);
                        this.sendSocketNotification("RECOMMEND_ERROR", { error: msg.message });
                    } else if (msg.type === "STATUS") {
                        console.log(`[MMM-FSS-Recommend] ${msg.message}`);
                    }
                } catch (e) {
                    // non-JSON output - ignore
                }
            }
        });

        this.pythonProcess.stderr.on("data", (data) => {
            console.error(`[MMM-FSS-Recommend] Python stderr: ${data.toString()}`);
        });

        this.pythonProcess.on("error", (err) => {
            console.error("[MMM-FSS-Recommend] Failed to start bridge:", err.message);
            this.sendSocketNotification("RECOMMEND_ERROR", { error: `Bridge start failed: ${err.message}` });
            this.started = false;
            this.pythonProcess = null;
        });

        this.pythonProcess.on("close", (code) => {
            console.warn(`[MMM-FSS-Recommend] Python bridge closed with code ${code}`);
            this.started = false;
            this.pythonProcess = null;
            this.processReady = false;
        });

        // Mark ready after a short delay (allow process to init)
        setTimeout(() => {
            if (this.pythonProcess && !this.pythonProcess.killed) {
                this.processReady = true;
                // Flush any pending searches
                for (const recipe of this.pendingQueue) {
                    this.sendSearch(recipe);
                }
                this.pendingQueue = [];
            }
        }, 500);

        this.started = true;
    },

    stop() {
        SessionLog.info("[MMM-FSS-Recommend] Node helper stopped");
        if (this.pythonProcess) {
            this.pythonProcess.kill("SIGTERM");
            setTimeout(() => {
                if (this.pythonProcess && !this.pythonProcess.killed) {
                    this.pythonProcess.kill("SIGKILL");
                }
            }, 3000);
        }
        this.pythonProcess = null;
        this.pendingQueue = [];
    }
});
