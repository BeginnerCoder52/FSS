#!/bin/bash
# run_e2e_tests.sh - FSS Automated System Test Runner

# Ensure we are in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================================="
echo "FSS Automated System Test Suite (Raspberry Pi Environment)"
echo "========================================================="

if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run this script with sudo (required for D-Bus System Bus)"
    exit 1
fi

# Determine which venv to use (DBDaemon usually has everything needed for D-Bus)
VENV_PATH="db_daemon/venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Error: Virtual environment not found at $VENV_PATH"
    echo "Please ensure the system is properly setup."
    exit 1
fi

echo "[INFO] Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "[INFO] pytest not found in venv. Installing pytest..."
    pip install pytest pytest-asyncio
fi

echo "[INFO] Running System Tests..."
echo ""

# Run pytest on the system_tests directory
pytest tests/system_tests/ -v

TEST_EXIT_CODE=$?

echo ""
echo "========================================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ ALL SYSTEM TESTS PASSED!"
else
    echo "❌ SOME TESTS FAILED. Please check the output above."
fi
echo "========================================================="

exit $TEST_EXIT_CODE
