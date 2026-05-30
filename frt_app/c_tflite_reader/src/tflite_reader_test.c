#include "TfliteReader.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void print_usage(const char* prog) {
    fprintf(stderr, "Usage: %s --model <path> --precision <fp32|fp16|int8>\n", prog);
}

static ModelPrecision parse_precision(const char* prec_str) {
    if (strcmp(prec_str, "fp32") == 0) return TFLITE_FP32;
    if (strcmp(prec_str, "fp16") == 0) return TFLITE_FP16;
    if (strcmp(prec_str, "int8") == 0) return TFLITE_INT8;
    fprintf(stderr, "Unknown precision '%s', defaulting to fp32\n", prec_str);
    return TFLITE_FP32;
}

int main(int argc, char** argv) {
    const char* model_path = NULL;
    ModelPrecision precision = TFLITE_FP32;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--model") == 0 && i + 1 < argc) {
            model_path = argv[++i];
        } else if (strcmp(argv[i], "--precision") == 0 && i + 1 < argc) {
            precision = parse_precision(argv[++i]);
        } else {
            print_usage(argv[0]);
            return 1;
        }
    }

    if (!model_path) {
        print_usage(argv[0]);
        return 1;
    }

    printf("TFLite Reader Test\n");
    printf("  Model:      %s\n", model_path);
    printf("  Precision:  %s\n",
           precision == TFLITE_FP32 ? "FP32" :
           precision == TFLITE_FP16 ? "FP16" : "INT8");

    TfliteReader* reader = tflite_reader_create(model_path, precision);
    if (!reader) {
        fprintf(stderr, "FAILED: tflite_reader_create returned NULL\n");
        return 1;
    }
    printf("  Reader:     CREATED\n");

    int dims[4] = {0};
    int num_dims = tflite_reader_get_input_dims(reader, dims, 4);
    if (num_dims < 0) {
        fprintf(stderr, "FAILED: tflite_reader_get_input_dims failed\n");
        tflite_reader_destroy(reader);
        return 1;
    }

    printf("  Input dims: [");
    for (int i = 0; i < num_dims; i++) {
        printf("%s%d", i > 0 ? ", " : "", dims[i]);
    }
    printf("]\n");

    int input_size = tflite_reader_get_input_size(reader);
    if (input_size < 0) {
        fprintf(stderr, "FAILED: tflite_reader_get_input_size failed\n");
        tflite_reader_destroy(reader);
        return 1;
    }
    printf("  Input size: %d bytes\n", input_size);

    void* dummy_input = calloc(1, (size_t)input_size);
    if (!dummy_input) {
        fprintf(stderr, "FAILED: could not allocate dummy input\n");
        tflite_reader_destroy(reader);
        return 1;
    }

    int ret = tflite_reader_run_inference(reader, dummy_input, (size_t)input_size);
    free(dummy_input);

    if (ret != 0) {
        fprintf(stderr, "FAILED: tflite_reader_run_inference returned %d\n", ret);
        tflite_reader_destroy(reader);
        return 1;
    }
    printf("  Inference:  OK\n");

    int num_outputs = 0;
    const float* output = tflite_reader_get_output(reader, &num_outputs);
    if (!output || num_outputs <= 0) {
        fprintf(stderr, "FAILED: tflite_reader_get_output returned NULL or empty\n");
        tflite_reader_destroy(reader);
        return 1;
    }
    printf("  Outputs:    %d values\n", num_outputs);
    printf("  First 5:    ");
    for (int i = 0; i < 5 && i < num_outputs; i++) {
        printf("%s%.6f", i > 0 ? ", " : "", output[i]);
    }
    printf("\n");

    ModelPrecision actual_prec = tflite_reader_get_precision(reader);
    printf("  Precision:  %s\n",
           actual_prec == TFLITE_FP32 ? "FP32" :
           actual_prec == TFLITE_FP16 ? "FP16" : "INT8");

    tflite_reader_destroy(reader);
    printf("  Destroyed:  OK\n");
    printf("ALL TESTS PASSED\n");

    return 0;
}
