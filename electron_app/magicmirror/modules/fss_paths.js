/**
 * @file fss_paths.js
 * @brief Shared path resolution utilities for FSS MagicMirror modules.
 *
 * Resolves Python executable paths dynamically instead of using hardcoded paths.
 * Search order:
 *   1. Module-local py_bridge/venv/bin/python3
 *   2. System python3
 */

const fs = require("fs");
const path = require("path");

/**
 * Resolve the Python executable for a MagicMirror module.
 * Tries module-local venv first, then falls back to system python3.
 *
 * @param {string} moduleDir - The __dirname of the calling module
 * @returns {string} Absolute path to python3 executable
 */
function resolvePythonExecutable(moduleDir) {
	const candidates = [
		path.join(moduleDir, "py_bridge", "venv", "bin", "python3"),
		"/usr/bin/python3",
	];

	for (const candidate of candidates) {
		if (fs.existsSync(candidate)) {
			return candidate;
		}
	}

	// Last resort: rely on PATH
	return "python3";
}

module.exports = { resolvePythonExecutable };
