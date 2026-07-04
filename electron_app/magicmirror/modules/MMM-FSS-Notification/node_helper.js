const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../js/session_logger");
const { resolvePythonExecutable } = require("../fss_paths");

module.exports = NodeHelper.create({
    start() {
        console.log(`${this.name}: Starting node helper`);
        SessionLog.info(`[${this.name}] Node helper started`);
        this.pythonProcess = null;
        this.isListening = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
    },

    socketNotificationReceived(notification, payload) {
        if (notification === "MMM_FSS_NOTIFICATION_START") {
            console.log(`${this.name}: Received start notification`);
            this.config = payload;
            this.startDBusListener();
        }
    },

    startDBusListener() {
        if (this.pythonProcess) {
            console.warn(`${this.name}: Python process already running`);
            return;
        }

        const pythonScriptPath = path.join(__dirname, "py_bridge", "notification_dbus_listener.py");

        if (!fs.existsSync(pythonScriptPath)) {
            console.error(`${this.name}: Python script not found at ${pythonScriptPath}`);
            return;
        }

        console.log(`${this.name}: Starting Python D-Bus listener from ${pythonScriptPath}`);

        try {
            const pythonExecutable = resolvePythonExecutable(__dirname);
            const args = [pythonScriptPath];

            this.pythonProcess = spawn(pythonExecutable, args, {
                stdio: ["pipe", "pipe", "pipe"],
                detached: false,
            });

            this.pythonProcess.stdout.on("data", (data) => {
                const message = data.toString().trim();
                console.log(`${this.name} [PY]: ${message}`);
                this.handlePythonOutput(message);
            });

            this.pythonProcess.stderr.on("data", (data) => {
                const error = data.toString().trim();
                console.error(`${this.name} [PY ERROR]: ${error}`);
            });

            this.pythonProcess.on("error", (err) => {
                console.error(`${this.name}: Process error - ${err.message}`);
                this.pythonProcess = null;
                this.isListening = false;
                this.attemptReconnect();
            });

            this.pythonProcess.on("close", (code) => {
                console.warn(`${this.name}: Python process exited with code ${code}`);
                this.pythonProcess = null;
                this.isListening = false;
                this.attemptReconnect();
            });

            this.isListening = true;
            this.reconnectAttempts = 0;
        } catch (error) {
            console.error(`${this.name}: Failed to start Python process - ${error.message}`);
            this.attemptReconnect();
        }
    },

    handlePythonOutput(message) {
        const lines = message.split("\n");
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const data = JSON.parse(line.trim());

                if (data.type === "FSS_NOTIFICATION") {
                    console.log(`${this.name}: Relaying FSS_NOTIFICATION - ${data.payload.message}`);
                    this.sendSocketNotification("FSS_NOTIFICATION", data.payload);
                } else if (data.type === "STATUS") {
                    console.log(`${this.name}: Status - ${data.message}`);
                }
            } catch (error) {
                console.debug(`${this.name}: Plain text message - ${line}`);
            }
        }
    },

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error(`${this.name}: Max reconnect attempts reached`);
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

        console.log(`${this.name}: Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.startDBusListener();
        }, delay);
    },

    stop() {
        SessionLog.info(`[${this.name}] Node helper stopped`);
        console.log(`${this.name}: Stopping node helper`);
        if (this.pythonProcess) {
            this.pythonProcess.kill("SIGTERM");
            setTimeout(() => {
                if (this.pythonProcess && !this.pythonProcess.killed) {
                    this.pythonProcess.kill("SIGKILL");
                }
            }, 3000);
        }
        this.pythonProcess = null;
    }
});
