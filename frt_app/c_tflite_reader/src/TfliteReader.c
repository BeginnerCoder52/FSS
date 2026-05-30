#include "TfliteReader.h"
#include "tensorflow/lite/c/c_api.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct TfliteReader {
    TfLiteModel* model;
    TfLiteInterpreterOptions* options;
    TfLiteInterpreter* interpreter;
    ModelPrecision precision;
    float* output_buffer;
    int output_size;
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

    TfLiteInterpreterOptionsSetNumThreads(reader->options, 2);

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
    } else if (output_type == kTfLiteInt8 || output_type == kTfLiteUInt8) {
        float scale = TfLiteTensorQuantizationParams(output_tensor);
        int zero_point = (int)TfLiteTensorQuantizationParams(output_tensor);
        zero_point = (int)((float)zero_point); 

        int num_elements = (int)(output_byte_size / sizeof(uint8_t));
        uint8_t* quantized = (uint8_t*)malloc(output_byte_size);
        if (!quantized) {
            log_error("failed to allocate quantized buffer");
            return -1;
        }

        TfLiteTensorCopyToBuffer(output_tensor, quantized, output_byte_size);

        reader->output_buffer = (float*)malloc((size_t)num_elements * sizeof(float));
        if (!reader->output_buffer) {
            log_error("failed to allocate dequantized buffer");
            free(quantized);
            return -1;
        }

        scale = TfLiteTensorQuantizationParams(output_tensor);

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

        float scale = TfLiteTensorQuantizationParams(output_tensor);

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

    free(reader);
}
