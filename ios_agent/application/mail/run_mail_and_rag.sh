#!/bin/bash

# Combined launcher: first run Mail GUI agent, then run Mail RAG analysis
#
# Usage:
#   ./run_mail_and_rag.sh
#   ./run_mail_and_rag.sh --wda-url http://192.168.1.10:8100 --max-rounds 80
#
# Notes:
#   - This script:
#       1) Runs the Mail pipeline (same as run_mail.sh, using pipeline.py)
#       2) Automatically finds the latest ios_logs/mail_task_*/screenshots directory
#       3) Runs rag_system.py on that screenshot directory
#   - RAG step will use its own default arguments (you can still set API_BASE, MODEL_NAME, etc. via env vars)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=== Step 1: Running Mail GUI agent (pipeline.py) ==="
python "${PROJECT_ROOT}/application/mail/pipeline.py" "$@"

echo
echo "=== Step 2: Locating latest Mail task screenshots ==="

LOG_ROOT="${PROJECT_ROOT}/ios_logs"

if [ ! -d "${LOG_ROOT}" ]; then
    echo "Error: Log root directory not found: ${LOG_ROOT}"
    echo "Make sure the Mail pipeline ran successfully and created ios_logs/*."
    exit 1
fi

# Find the most recent mail_task_* directory under ios_logs
LATEST_TASK_DIR="$(ls -dt "${LOG_ROOT}"/mail_task_*/ 2>/dev/null | head -n 1 || true)"

if [ -z "${LATEST_TASK_DIR}" ]; then
    echo "Error: No mail_task_* directories found under ${LOG_ROOT}"
    echo "Cannot determine screenshot directory for RAG analysis."
    exit 1
fi

LATEST_TASK_DIR="${LATEST_TASK_DIR%/}"
SCREENSHOT_DIR="${LATEST_TASK_DIR}/screenshots"

if [ ! -d "${SCREENSHOT_DIR}" ]; then
    echo "Error: Screenshot directory not found: ${SCREENSHOT_DIR}"
    echo "Expected screenshots to be saved there by the Mail pipeline."
    exit 1
fi

echo "Using screenshot directory: ${SCREENSHOT_DIR}"

echo
echo "=== Step 3: Running Mail Screenshot RAG analysis (rag_system.py) ==="

python "${SCRIPT_DIR}/rag_system.py" --screenshot-dir "${SCREENSHOT_DIR}"

echo
echo "✅ Mail GUI agent + RAG analysis pipeline completed."

