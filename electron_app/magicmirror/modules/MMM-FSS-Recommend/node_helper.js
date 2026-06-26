const NodeHelper = require("node_helper");
const { spawn, execSync } = require("child_process");
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
        // this.httpServerProcess = null;
        // this.httpServerReady = false;
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
        } else if (notification === "GET_RECIPES") {
            if (!this.started) {
                this.startBridge();
            }
            if (this.processReady && this.pythonProcess && !this.pythonProcess.killed) {
                this.pythonProcess.stdin.write(JSON.stringify({ type: "GET_RECIPES" }) + "\n");
            }
        // } else if (notification === "GENERATE_QR") {
        //     this.handleGenerateQR(payload);
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
                    } else if (msg.type === "RECIPES") {
                        this.sendSocketNotification("RECIPES", { data: msg.data });
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
                // Fetch available recipes list
                this.pythonProcess.stdin.write(JSON.stringify({ type: "GET_RECIPES" }) + "\n");
            }
        }, 500);

        this.started = true;
    },

    /*
    startHttpServer() {
        if (this.httpServerProcess) {
            this.httpServerReady = true;
            return;
        }
        const script = path.join(__dirname, "py_bridge", "recipe_http_server.py");
        if (!fs.existsSync(script)) {
            console.error("[MMM-FSS-Recommend] HTTP server script not found");
            return;
        }
        const pythonExec = resolvePythonExecutable(__dirname);
        this.httpServerProcess = spawn(pythonExec, [script, "8081"], {
            stdio: ["pipe", "pipe", "pipe"],
            detached: false,
        });
        this.httpServerProcess.stderr.on("data", (data) => {
            console.log(`[RecipeHTTP] ${data.toString().trim()}`);
        });
        this.httpServerProcess.on("error", (err) => {
            console.error("[MMM-FSS-Recommend] HTTP server error:", err.message);
            this.httpServerProcess = null;
            this.httpServerReady = false;
        });
        this.httpServerProcess.on("close", (code) => {
            console.warn(`[MMM-FSS-Recommend] HTTP server exited with code ${code}`);
            this.httpServerProcess = null;
            this.httpServerReady = false;
        });
        setTimeout(() => { this.httpServerReady = true; }, 1500);
    },

    handleGenerateQR(recipeData) {
        if (!this.httpServerReady) {
            this.startHttpServer();
            setTimeout(() => this.handleGenerateQR(recipeData), 2000);
            return;
        }
        const httpUrl = `http://127.0.0.1:8081/api/recipe`;
        const body = JSON.stringify(recipeData);
        try {
            const result = execSync(
                `curl -s -X POST "${httpUrl}" -H "Content-Type: application/json" -d '${body.replace(/'/g, "'\\''")}'`,
                { timeout: 5000 }
            );
            const resp = JSON.parse(result.toString());
            if (!resp.url) {
                this.sendSocketNotification("QR_ERROR", { error: "No URL returned" });
                return;
            }
            // Generate QR code from URL
            const qrScript = path.join(__dirname, "py_bridge", "qr_generator.py");
            const pythonExec = resolvePythonExecutable(__dirname);
            const qrProcess = spawn(pythonExec, [qrScript]);
            let qrOut = "";
            qrProcess.stdout.on("data", (d) => { qrOut += d.toString(); });
            qrProcess.on("close", () => {
                try {
                    const qrMsg = JSON.parse(qrOut.trim());
                    if (qrMsg.type === "QR_DATA") {
                        this.sendSocketNotification("QR_CODE_READY", {
                            base64: qrMsg.base64,
                            url: resp.url
                        });
                    } else {
                        this.sendSocketNotification("QR_ERROR", { error: qrMsg.message || "QR generation failed" });
                    }
                } catch (e) {
                    this.sendSocketNotification("QR_ERROR", { error: "Failed to parse QR output" });
                }
            });
            qrProcess.stdin.write(JSON.stringify({ url: resp.url }) + "\n");
            qrProcess.stdin.end();
        } catch (e) {
            this.sendSocketNotification("QR_ERROR", { error: `HTTP request failed: ${e.message}` });
        }
    },
    */

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
        /*
        if (this.httpServerProcess) {
            this.httpServerProcess.kill("SIGTERM");
            setTimeout(() => {
                if (this.httpServerProcess && !this.httpServerProcess.killed) {
                    this.httpServerProcess.kill("SIGKILL");
                }
            }, 3000);
        }
        */
        this.pythonProcess = null;
        // this.httpServerProcess = null;
        this.pendingQueue = [];
    }
});
