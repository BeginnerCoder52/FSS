const fs = require("node:fs");
const path = require("node:path");

const LOG_DIR = path.resolve(__dirname, "../logs");

if (!fs.existsSync(LOG_DIR)) {
    try {
        fs.mkdirSync(LOG_DIR, { recursive: true });
    } catch (e) {}
}

function getDateStr() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function getTimestamp() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

const logFile = path.join(LOG_DIR, `session_${getDateStr()}.log`);
const sessionId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

function writeLog(level, message) {
    try {
        const line = `[${getTimestamp()}] [${sessionId}] [${level}] ${message}\n`;
        fs.appendFileSync(logFile, line);
    } catch (e) {}
}

module.exports = {
    sessionId,
    logFile,
    info: (msg) => writeLog("INFO", msg),
    warn: (msg) => writeLog("WARN", msg),
    error: (msg) => writeLog("ERROR", msg),
    debug: (msg) => writeLog("DEBUG", msg),
};
