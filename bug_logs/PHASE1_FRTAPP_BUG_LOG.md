# Phase 1 — FRTApp Model Test Bug Log

## Bug 1: INT8 Dequantization — False Detections (1320 outputs)

**Severity**: Critical
**Component**: `c_tflite_reader/src/TfliteReader.c`
**Discovered**: 2026-06-07, `test_model_benchmark.py` run on Pi 4B

**Symptoms**: Model returned 1320 detections on a single-carrot image. NMS was unable to filter because confidence scores were corrupted — background pixels scored above 0.2 threshold.

**Root Cause**: `tflite_reader_run_inference()` handled both `kTfLiteInt8` and `kTfLiteUInt8` output types with a single `uint8_t*` buffer. For `kTfLiteInt8`, raw bytes are signed (-128 to 127), but reading them as `uint8_t` (0-255) shifted all dequantized values by 128×scale, pushing background activations into detection territory.

**Fix**: Split `kTfLiteInt8` and `kTfLiteUInt8` into separate branches. For `kTfLiteInt8`, allocate `int8_t*` buffer and read signed values before dequantization.

**File(s) changed**: `frt_app/c_tflite_reader/src/TfliteReader.c` (lines 226-252)

---

## Bug 2: High Latency (594ms vs 150ms target)

**Severity**: High
**Component**: `c_tflite_reader/src/TfliteReader.c`
**Discovered**: 2026-06-07, `test_model_benchmark.py` run on Pi 4B

**Symptoms**: INT8 inference took 594ms on Pi 4B — 4× the 150ms target.

**Root Causes**:
1. Thread count set to 2 (`TfLiteInterpreterOptionsSetNumThreads(2)`) — Pi 4B has 4 cores
2. Missing XNNPACK delegate registration — without it, INT8 models fall back to slow CPU kernels instead of accelerated XNNPACK path

**Fixes**:
- Thread count increased to 4
- Added XNNPACK delegate registration with CMake detection (`HAVE_XNNPACK`)
- Wrapped in `#ifdef HAVE_XNNPACK` for portable compilation

**File(s) changed**: `frt_app/c_tflite_reader/src/TfliteReader.c`, `frt_app/c_tflite_reader/CMakeLists.txt`

**Expected result**: 80-150ms with XNNPACK enabled.

---

## Bug 3: Missing Preprocessing in C Backend

**Severity**: Medium
**Component**: `c_tflite_reader/src/TfliteReader.c`, `py_ai_core/src/YoloTfliteEngine.py`
**Discovered**: 2026-06-07, code review

**Symptoms**: Raw camera frames (640×480 BGR) could not be fed directly to the C backend. Caller had to preprocess in Python (resize to 640×640, BGR→RGB, normalize) before calling `tflite_reader_run_inference`. This defeated the purpose of having a C backend.

**Root Cause**: C library had no preprocessing API — only accepted pre-formatted tensors.

**Fix**: Added `tflite_reader_preprocess_and_run()` to C library:
- Accepts raw BGR frame at any resolution
- Letterbox-resizes to model input dimensions (640×640) with bilinear interpolation
- Converts BGR→RGB during pixel copy
- Normalizes to [0,1] for float32 models or keeps uint8 for quantized models
- Runs inference

Python `YoloTfliteEngine.preprocess_and_run()` wraps this via ctypes. Test script auto-detects availability.

**File(s) changed**: `frt_app/c_tflite_reader/src/TfliteReader.c`, `frt_app/c_tflite_reader/include/TfliteReader.h`, `frt_app/py_ai_core/src/YoloTfliteEngine.py`, `frt_app/tests/test_model_benchmark.py`
