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
	const candidates = [];
	if (process.env.VIRTUAL_ENV) {
		candidates.push(path.join(process.env.VIRTUAL_ENV, "bin", "python3"));
	}

	// Dynamic traversal to find project-level .venv
	let dir = moduleDir;
	while (dir && dir !== path.parse(dir).root) {
		const workspaceVenv = path.join(dir, ".venv", "bin", "python3");
		if (fs.existsSync(workspaceVenv)) {
			candidates.push(workspaceVenv);
		}
		dir = path.dirname(dir);
	}

	candidates.push(path.join(moduleDir, "py_bridge", "venv", "bin", "python3"));
	candidates.push("/usr/bin/python3");

	for (const candidate of candidates) {
		if (fs.existsSync(candidate)) {
			return candidate;
		}
	}

	// Last resort: rely on PATH
	return "python3";
}

module.exports = { resolvePythonExecutable };
