#include "TfliteReader.h"
#include "tensorflow/lite/c/c_api.h"
#ifdef HAVE_XNNPACK
#include "tensorflow/lite/delegates/xnnpack/xnnpack_delegate.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

struct TfliteReader {
    TfLiteModel* model;
    TfLiteInterpreterOptions* options;
    TfLiteInterpreter* interpreter;
    ModelPrecision precision;
    float* output_buffer;
    int output_size;
    TfLiteDelegate* xnnpack_delegate;
    int input_width;
    int input_height;
    TfLiteType input_type;
};

static void log_error(const char* msg) {
    fprintf(stderr, "TfliteReader: %s\n", msg);
}

TfliteReader* tflite_reader_create(const char* model_path, ModelPrecision precision) {
    if (!model_path) {
        log_error("model_path is NULL");
        return NULL;
    }

    TfliteReader* reader = (TfliteReader*)calloc(1, sizeof(TfliteReader));
    if (!reader) {
        log_error("failed to allocate TfliteReader");
        return NULL;
    }

    reader->precision = precision;
    reader->output_buffer = NULL;
    reader->output_size = 0;
    reader->xnnpack_delegate = NULL;

    reader->model = TfLiteModelCreateFromFile(model_path);
    if (!reader->model) {
        log_error("failed to create TfLiteModel");
        free(reader);
        return NULL;
    }

    reader->options = TfLiteInterpreterOptionsCreate();
    if (!reader->options) {
        log_error("failed to create TfLiteInterpreterOptions");
        TfLiteModelDelete(reader->model);
        free(reader);
        return NULL;
    }

    TfLiteInterpreterOptionsSetNumThreads(reader->options, 4);

#ifdef HAVE_XNNPACK
    TfLiteXNNPackDelegateOptions xnnpack_opts = TfLiteXNNPackDelegateOptionsDefault();
    reader->xnnpack_delegate = TfLiteXNNPackDelegateCreate(&xnnpack_opts);
    if (reader->xnnpack_delegate) {
        TfLiteInterpreterOptionsAddDelegate(reader->options, reader->xnnpack_delegate);
    } else {
        fprintf(stderr, "TfliteReader: XNNPACK delegate not available, using fallback\n");
    }
#else
    fprintf(stderr, "TfliteReader: XNNPACK not compiled, using fallback CPU kernels\n");
#endif

    reader->interpreter = TfLiteInterpreterCreate(reader->model, reader->options);
    if (!reader->interpreter) {
        log_error("failed to create TfLiteInterpreter");
        TfLiteInterpreterOptionsDelete(reader->options);
        TfLiteModelDelete(reader->model);
        free(reader);
        return NULL;
    }

    if (TfLiteInterpreterAllocateTensors(reader->interpreter) != kTfLiteOk) {
        log_error("failed to allocate tensors");
        tflite_reader_destroy(reader);
        return NULL;
    }

    const TfLiteTensor* input_tensor = TfLiteInterpreterGetInputTensor(reader->interpreter, 0);
    if (input_tensor) {
        reader->input_height = TfLiteTensorDim(input_tensor, 1);
        reader->input_width  = TfLiteTensorDim(input_tensor, 2);
        reader->input_type   = TfLiteTensorType(input_tensor);
    }

    return reader;
}

int tflite_reader_get_input_dims(TfliteReader* reader, int* dims_out, int max_dims) {
    if (!reader || !reader->interpreter || !dims_out) {
        log_error("invalid arguments for get_input_dims");
        return -1;
    }

    int input_count = TfLiteInterpreterGetInputTensorCount(reader->interpreter);
    if (input_count < 1) {
        log_error("no input tensors");
        return -1;
    }

    const TfLiteTensor* input_tensor = TfLiteInterpreterGetInputTensor(reader->interpreter, 0);
    if (!input_tensor) {
        log_error("failed to get input tensor");
        return -1;
    }

    int num_dims = TfLiteTensorNumDims(input_tensor);
    if (num_dims > max_dims) {
        num_dims = max_dims;
    }

    for (int i = 0; i < num_dims; i++) {
        dims_out[i] = TfLiteTensorDim(input_tensor, i);
    }

    return num_dims;
}

int tflite_reader_get_input_size(TfliteReader* reader) {
    if (!reader || !reader->interpreter) {
        log_error("invalid arguments for get_input_size");
        return -1;
    }

    int input_count = TfLiteInterpreterGetInputTensorCount(reader->interpreter);
    if (input_count < 1) {
        log_error("no input tensors");
        return -1;
    }

    const TfLiteTensor* input_tensor = TfLiteInterpreterGetInputTensor(reader->interpreter, 0);
    if (!input_tensor) {
        log_error("failed to get input tensor for size");
        return -1;
    }

    return TfLiteTensorByteSize(input_tensor);
}

int tflite_reader_run_inference(TfliteReader* reader, const void* input_data, size_t input_size) {
    if (!reader || !reader->interpreter || !input_data) {
        log_error("invalid arguments for run_inference");
        return -1;
    }

    const TfLiteTensor* input_tensor = TfLiteInterpreterGetInputTensor(reader->interpreter, 0);
    if (!input_tensor) {
        log_error("failed to get input tensor for inference");
        return -1;
    }

    size_t expected_size = (size_t)TfLiteTensorByteSize(input_tensor);
    if (input_size != expected_size) {
        log_error("input size mismatch");
        return -1;
    }

    TfLiteStatus status = TfLiteTensorCopyFromBuffer(
        (TfLiteTensor*)input_tensor, input_data, input_size
    );
    if (status != kTfLiteOk) {
        log_error("failed to copy input data to tensor");
        return -1;
    }

    status = TfLiteInterpreterInvoke(reader->interpreter);
    if (status != kTfLiteOk) {
        log_error("inference invocation failed");
        return -1;
    }

    const TfLiteTensor* output_tensor = TfLiteInterpreterGetOutputTensor(
        reader->interpreter, 0
    );
    if (!output_tensor) {
        log_error("failed to get output tensor");
        return -1;
    }

    size_t output_byte_size = (size_t)TfLiteTensorByteSize(output_tensor);
    TfLiteType output_type = TfLiteTensorType(output_tensor);

    if (reader->output_buffer) {
        free(reader->output_buffer);
        reader->output_buffer = NULL;
    }

    if (output_type == kTfLiteFloat32) {
        int num_floats = (int)(output_byte_size / sizeof(float));
        reader->output_buffer = (float*)malloc(output_byte_size);
        if (!reader->output_buffer) {
            log_error("failed to allocate output buffer");
            return -1;
        }
        TfLiteTensorCopyToBuffer(output_tensor, reader->output_buffer, output_byte_size);
        reader->output_size = num_floats;
    } else if (output_type == kTfLiteUInt8) {
        TfLiteQuantizationParams quant_params = TfLiteTensorQuantizationParams(output_tensor);
        float scale = quant_params.scale;
        int zero_point = quant_params.zero_point;

        int num_elements = (int)(output_byte_size / sizeof(uint8_t));
        uint8_t* quantized = (uint8_t*)malloc(output_byte_size);
        if (!quantized) {
            log_error("failed to allocate uint8 buffer");
            return -1;
        }

        TfLiteTensorCopyToBuffer(output_tensor, quantized, output_byte_size);

        reader->output_buffer = (float*)malloc((size_t)num_elements * sizeof(float));
        if (!reader->output_buffer) {
            log_error("failed to allocate dequantized buffer");
            free(quantized);
            return -1;
        }

        for (int i = 0; i < num_elements; i++) {
            reader->output_buffer[i] = (float)((int)quantized[i] - zero_point) * scale;
        }

        free(quantized);
        reader->output_size = num_elements;

    } else if (output_type == kTfLiteInt8) {
        TfLiteQuantizationParams quant_params = TfLiteTensorQuantizationParams(output_tensor);
        float scale = quant_params.scale;
        int zero_point = quant_params.zero_point;

        int num_elements = (int)(output_byte_size / sizeof(int8_t));
        int8_t* quantized = (int8_t*)malloc(output_byte_size);
        if (!quantized) {
            log_error("failed to allocate int8 buffer");
            return -1;
        }

        TfLiteTensorCopyToBuffer(output_tensor, quantized, output_byte_size);

        reader->output_buffer = (float*)malloc((size_t)num_elements * sizeof(float));
        if (!reader->output_buffer) {
            log_error("failed to allocate dequantized buffer");
            free(quantized);
            return -1;
        }

        for (int i = 0; i < num_elements; i++) {
            reader->output_buffer[i] = (float)((int)quantized[i] - zero_point) * scale;
        }

        free(quantized);
        reader->output_size = num_elements;
    } else if (output_type == kTfLiteInt16) {
        int num_elements = (int)(output_byte_size / sizeof(int16_t));
        int16_t* int16_buf = (int16_t*)malloc(output_byte_size);
        if (!int16_buf) {
            log_error("failed to allocate int16 buffer");
            return -1;
        }

        TfLiteTensorCopyToBuffer(output_tensor, int16_buf, output_byte_size);

        float scale = TfLiteTensorQuantizationParams(output_tensor).scale;

        reader->output_buffer = (float*)malloc((size_t)num_elements * sizeof(float));
        if (!reader->output_buffer) {
            log_error("failed to allocate fp32 buffer for int16");
            free(int16_buf);
            return -1;
        }

        for (int i = 0; i < num_elements; i++) {
            reader->output_buffer[i] = (float)int16_buf[i] * scale;
        }

        free(int16_buf);
        reader->output_size = num_elements;
    } else {
        log_error("unsupported output tensor type");
        return -1;
    }

    return 0;
}

int tflite_reader_preprocess_and_run(
    TfliteReader* reader,
    const unsigned char* bgr_frame,
    int frame_width,
    int frame_height)
{
    if (!reader || !reader->interpreter || !bgr_frame || frame_width <= 0 || frame_height <= 0) {
        log_error("invalid arguments for preprocess_and_run");
        return -1;
    }

    int target_w = reader->input_width;
    int target_h = reader->input_height;
    if (target_w <= 0 || target_h <= 0) {
        log_error("model input dimensions not initialized");
        return -1;
    }

    float scale = (float)target_w / (float)frame_width;
    float scale_h = (float)target_h / (float)frame_height;
    if (scale_h < scale) scale = scale_h;

    int resized_w = (int)(frame_width * scale);
    int resized_h = (int)(frame_height * scale);
    if (resized_w < 1) resized_w = 1;
    if (resized_h < 1) resized_h = 1;

    int pad_top  = (target_h - resized_h) / 2;
    int pad_left = (target_w - resized_w) / 2;

    unsigned char* canvas = (unsigned char*)malloc((size_t)target_w * target_h * 3);
    if (!canvas) {
        log_error("failed to allocate canvas for preprocessing");
        return -1;
    }

    memset(canvas, 114, (size_t)target_w * target_h * 3);

    for (int y = 0; y < resized_h; y++) {
        float src_y = (float)y / scale;
        int src_y0 = (int)src_y;
        int src_y1 = src_y0 + 1;
        if (src_y1 >= frame_height) src_y1 = frame_height - 1;
        float fy = src_y - src_y0;

        for (int x = 0; x < resized_w; x++) {
            float src_x = (float)x / scale;
            int src_x0 = (int)src_x;
            int src_x1 = src_x0 + 1;
            if (src_x1 >= frame_width) src_x1 = frame_width - 1;
            float fx = src_x - src_x0;

            int dst_idx = ((pad_top + y) * target_w + (pad_left + x)) * 3;

            for (int c = 0; c < 3; c++) {
                int src_c = 2 - c;
                float v00 = bgr_frame[(src_y0 * frame_width + src_x0) * 3 + src_c];
                float v10 = bgr_frame[(src_y0 * frame_width + src_x1) * 3 + src_c];
                float v01 = bgr_frame[(src_y1 * frame_width + src_x0) * 3 + src_c];
                float v11 = bgr_frame[(src_y1 * frame_width + src_x1) * 3 + src_c];

                float top = v00 + (v10 - v00) * fx;
                float bot = v01 + (v11 - v01) * fx;
                float val = top + (bot - top) * fy;

                canvas[dst_idx + c] = (unsigned char)(val + 0.5f);
            }
        }
    }

    const TfLiteTensor* input_tensor = TfLiteInterpreterGetInputTensor(reader->interpreter, 0);
    if (!input_tensor) {
        log_error("failed to get input tensor");
        free(canvas);
        return -1;
    }

    size_t expected = (size_t)TfLiteTensorByteSize(input_tensor);
    int ret = -1;

    if (reader->input_type == kTfLiteFloat32) {
        size_t num_pixels = (size_t)target_w * target_h * 3;
        float* float_input = (float*)malloc(num_pixels * sizeof(float));
        if (!float_input) {
            log_error("failed to allocate float input buffer");
            free(canvas);
            return -1;
        }
        for (size_t i = 0; i < num_pixels; i++) {
            float_input[i] = canvas[i] * (1.0f / 255.0f);
        }
        ret = tflite_reader_run_inference(reader, float_input, num_pixels * sizeof(float));
        free(float_input);
    } else {
        ret = tflite_reader_run_inference(reader, canvas, (size_t)target_w * target_h * 3);
    }

    free(canvas);
    return ret;
}


const float* tflite_reader_get_output(TfliteReader* reader, int* num_detections_out) {
    if (!reader || !num_detections_out) {
        log_error("invalid arguments for get_output");
        return NULL;
    }

    if (!reader->output_buffer) {
        log_error("no output buffer available - run inference first");
        *num_detections_out = 0;
        return NULL;
    }

    *num_detections_out = reader->output_size;
    return reader->output_buffer;
}

ModelPrecision tflite_reader_get_precision(TfliteReader* reader) {
    if (!reader) {
        log_error("reader is NULL in get_precision");
        return TFLITE_FP32;
    }
    return reader->precision;
}

void tflite_reader_destroy(TfliteReader* reader) {
    if (!reader) return;

    if (reader->interpreter) {
        TfLiteInterpreterDelete(reader->interpreter);
    }
    if (reader->options) {
        TfLiteInterpreterOptionsDelete(reader->options);
    }
    if (reader->model) {
        TfLiteModelDelete(reader->model);
    }
    if (reader->output_buffer) {
        free(reader->output_buffer);
    }
#ifdef HAVE_XNNPACK
    if (reader->xnnpack_delegate) {
        TfLiteXNNPackDelegateDelete(reader->xnnpack_delegate);
    }
#endif

    free(reader);
}
