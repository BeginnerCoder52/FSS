#ifndef TFLITE_READER_H
#define TFLITE_READER_H

#include <stddef.h>

typedef enum {
    TFLITE_FP32 = 0,
    TFLITE_FP16 = 1,
    TFLITE_INT8 = 2
} ModelPrecision;

typedef struct TfliteReader TfliteReader;

TfliteReader* tflite_reader_create(const char* model_path, ModelPrecision precision);

int tflite_reader_get_input_dims(TfliteReader* reader, int* dims_out, int max_dims);

int tflite_reader_get_input_size(TfliteReader* reader);

int tflite_reader_run_inference(TfliteReader* reader, const void* input_data, size_t input_size);

int tflite_reader_preprocess_and_run(
    TfliteReader* reader,
    const unsigned char* bgr_frame,
    int frame_width,
    int frame_height
);

const float* tflite_reader_get_output(TfliteReader* reader, int* num_detections_out);

ModelPrecision tflite_reader_get_precision(TfliteReader* reader);

void tflite_reader_destroy(TfliteReader* reader);

#endif /* TFLITE_READER_H */
