#!/usr/bin/env bash
# ==============================================================================
# deploy_model.sh — Deploy YOLO model to FSS runtime directory
# ==============================================================================
#
# Downloads (or copies) a TFLite model to /opt/fss/models/ with optional
# SHA256 checksum verification and version tracking.
#
# Usage:
#   bash tools/deploy-model/deploy_model.sh                     # Download default
#   bash tools/deploy-model/deploy_model.sh --local /path/to/model.tflite  # Local copy
#   bash tools/deploy-model/deploy_model.sh --skip-if-exists    # Skip if model present
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FSS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source profile
. "$FSS_ROOT/fss_profile.conf"

# --- Parse arguments ---------------------------------------------------------
LOCAL_MODEL_PATH=""
SKIP_IF_EXISTS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --local)
            LOCAL_MODEL_PATH="$2"
            shift 2
            ;;
        --skip-if-exists)
            SKIP_IF_EXISTS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--local /path/to/model.tflite] [--skip-if-exists]"
            exit 0
            ;;
        *)
            fss_log_error "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# --- Check if model already exists -------------------------------------------
if [[ "$SKIP_IF_EXISTS" == true && -f "$FSS_MODEL_PATH" ]]; then
    fss_log_skip "Model already exists at $FSS_MODEL_PATH"
    exit 0
fi

# --- Ensure target directory exists ------------------------------------------
mkdir -p "$FSS_MODEL_DIR"

# --- Deploy model ------------------------------------------------------------
if [[ -n "$LOCAL_MODEL_PATH" ]]; then
    # Local file copy
    if [[ ! -f "$LOCAL_MODEL_PATH" ]]; then
        fss_log_error "Local model not found: $LOCAL_MODEL_PATH"
        exit 1
    fi
    fss_log_info "Copying local model: $LOCAL_MODEL_PATH -> $FSS_MODEL_PATH"
    cp "$LOCAL_MODEL_PATH" "$FSS_MODEL_PATH"
else
    # Download from GitHub Releases
    MODEL_URL="${FSS_MODEL_URL_BASE}/${FSS_MODEL_VERSION}/${FSS_MODEL_FILE}"
    fss_log_info "Downloading model from: $MODEL_URL"

    TEMP_FILE=$(mktemp)
    trap "rm -f $TEMP_FILE" EXIT

    MAX_RETRIES=3
    for attempt in $(seq 1 $MAX_RETRIES); do
        if wget -q --show-progress -O "$TEMP_FILE" "$MODEL_URL" 2>/dev/null || \
           curl -fSL -o "$TEMP_FILE" "$MODEL_URL" 2>/dev/null; then
            fss_log_ok "Download successful (attempt $attempt/$MAX_RETRIES)"
            break
        else
            if [[ $attempt -eq $MAX_RETRIES ]]; then
                fss_log_error "Download failed after $MAX_RETRIES attempts."
                fss_log_error "URL: $MODEL_URL"
                fss_log_error "Try: bash $0 --local /path/to/model.tflite"
                exit 1
            fi
            fss_log_warn "Download attempt $attempt failed, retrying in 5s..."
            sleep 5
        fi
    done

    mv "$TEMP_FILE" "$FSS_MODEL_PATH"
fi

# --- Verify checksum ---------------------------------------------------------
if [[ -n "$FSS_MODEL_CHECKSUM" ]]; then
    fss_log_info "Verifying SHA256 checksum..."
    ACTUAL_CHECKSUM=$(sha256sum "$FSS_MODEL_PATH" | awk '{print $1}')
    if [[ "$ACTUAL_CHECKSUM" == "$FSS_MODEL_CHECKSUM" ]]; then
        fss_log_ok "Checksum verified: $ACTUAL_CHECKSUM"
    else
        fss_log_error "Checksum MISMATCH!"
        fss_log_error "  Expected: $FSS_MODEL_CHECKSUM"
        fss_log_error "  Actual:   $ACTUAL_CHECKSUM"
        rm -f "$FSS_MODEL_PATH"
        exit 1
    fi
else
    fss_log_warn "No checksum configured (FSS_MODEL_CHECKSUM empty), skipping verification"
fi

# --- Verify file is non-empty ------------------------------------------------
FILE_SIZE=$(stat --format=%s "$FSS_MODEL_PATH" 2>/dev/null || stat -f%z "$FSS_MODEL_PATH" 2>/dev/null || echo 0)
if [[ "$FILE_SIZE" -eq 0 ]]; then
    fss_log_error "Model file is empty!"
    rm -f "$FSS_MODEL_PATH"
    exit 1
fi

# --- Version tracking --------------------------------------------------------
echo "$FSS_MODEL_VERSION" > "${FSS_MODEL_DIR}/.model_version"
fss_log_ok "Model deployed: $FSS_MODEL_PATH ($FILE_SIZE bytes, version $FSS_MODEL_VERSION)"
