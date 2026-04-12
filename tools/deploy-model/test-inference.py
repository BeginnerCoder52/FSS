import os
import csv
import cv2
import numpy as np
import json
import re
import time
from tflite_runtime.interpreter import Interpreter

class YoloTfliteEngine:
    def __init__(self, model_path, conf_thresh=0.5):
        """Khởi tạo Engine suy luận TFLite"""
        print(f"[INFO] Đang tải mô hình từ: {model_path}...")
        # Tải mô hình với cài đặt num_thread2=2
        self.interpreter = Interpreter(
            model_path=model_path,
            num_threads=2   # =4 x1.5 =1; =2 x0.5 =1; =3 >~ =1
        )
        # Chuẩn bị bộ nhớ
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.conf_thresh = conf_thresh
        
        # Lấy kích thước đầu vào yêu cầu của mô hình
        self.input_shape = self.input_details[0]['shape']
        self.input_height = self.input_shape[1]
        self.input_width = self.input_shape[2]
        self.is_int8 = self.input_details[0]['dtype'] == np.int8
        
        # Lấy thông số lượng tử hóa
        self.input_scale, self.input_zero_point = self.input_details[0]['quantization']

        output_shape = self.output_details[0]['shape']
        self.num_attrs = min(output_shape[1], output_shape[2])
        self.num_classes = self.num_attrs - 4
        print(f"[INFO] Model: {self.num_classes} classes, output shape: {output_shape}")
        print(f"[INFO] Quantization: {'INT8' if self.is_int8 else 'Float32'}")

    def letterbox(self, img, new_shape, color=(114, 114, 114)):
        """Áp dụng Letterboxing để giữ nguyên tỷ lệ khung hình"""
        shape = img.shape[:2]  # [height, width]
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        dw /= 2  # Chia đều padding ra 2 bên
        dh /= 2
        
        if shape[::-1] != new_unpad:
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
            
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img, r, (dw, dh)

    def preprocess(self, img_path):
        """Tiền xử lý hình ảnh đầu vào"""
        img0 = cv2.imread(img_path)
        if img0 is None:
            raise ValueError(f"[ERROR] Không thể đọc ảnh: {img_path}")
            
        # 1. Chuyển đổi không gian màu sang RGB
        img = cv2.cvtColor(img0, cv2.COLOR_BGR2RGB)
        
        # 2. Áp dụng Letterbox
        img_letterboxed, ratio, pad = self.letterbox(img, (self.input_height, self.input_width))
        
        # 3. Chuẩn bị Input Tensor (Zero-copy input feed qua Numpy)
        img_input = img_letterboxed.astype(np.float32) / 255.0  # Chuẩn hóa [0.0, 1.0]
        
        # Nếu mô hình là Full INT8 (cả Input cũng lượng tử hóa)
        if self.is_int8 and self.input_scale != 0:
            img_input = (img_input / self.input_scale) + self.input_zero_point
            img_input = img_input.astype(np.int8)
            
        img_input = np.expand_dims(img_input, axis=0) # [1, 640, 640, 3]
        return img_input, img0, ratio, pad

    def infer(self, img_path):
        """Thực thi suy luận và trả về kết quả JSON"""
        # Tiền xử lý
        input_data, original_img, ratio, pad = self.preprocess(img_path)
        
        # Set tensor (Truyền vùng nhớ thẳng vào TFLite)
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        
        # Tiến hành suy luận đo thời gian
        start_time = time.time()
        self.interpreter.invoke()
        infer_time = (time.time() - start_time) * 1000
        fps = 1000 / infer_time
        
        # Lấy output
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        # Giải mã output (Ví dụ cơ bản, phụ thuộc vào việc mô hình có nhúng NMS chưa)
        # Nếu Ultralytics YOLOv11 xuất TFLite mặc định, mảng output thường là [1, num_classes + 4, num_boxes]
        out_scale, out_zero = self.output_details[0]['quantization']
        if self.is_int8 and out_scale != 0:
            output_data = (output_data.astype(np.float32) - out_zero) * out_scale
               
        squeezed = np.squeeze(output_data)
        if squeezed.shape[0] < squeezed.shape[1]:
            predictions = squeezed.T
        else:
            predictions = squeezed
        print(f"[DEBUG] squeezed shape: {squeezed.shape} → predictions shape: {predictions.shape}")

        results = []
        boxes_for_nms = []
        scores_for_nms = []
        class_ids = []
        for pred in predictions:
            classes_scores = pred[4:]
            class_id = np.argmax(classes_scores)
            confidence = float(classes_scores[class_id])
            
            # Lọc kết quả với Confidence score > 0.5
            if confidence > self.conf_thresh:
                xc, yc, w, h = pred[0], pred[1], pred[2], pred[3]
                print(f"[DEBUG] raw xc={xc:.4f} yc={yc:.4f} w={w:.4f} h={h:.4f}")
                
                # Scale to pixel of input tensor
                if xc <= 1.0 and yc <= 1.0:
                    xc *= self.input_width
                    yc *= self.input_height
                    w  *= self.input_width
                    h  *= self.input_height

                x1 = int(((xc - w/2) - pad[0]) / ratio)
                y1 = int(((yc - h/2) - pad[1]) / ratio)
                x2 = int(((xc + w/2) - pad[0]) / ratio)
                y2 = int(((yc + h/2) - pad[1]) / ratio)

                h_img, w_img = original_img.shape[:2]
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w_img, x2)
                y2 = min(h_img, y2)
                
                boxes_for_nms.append([x1, y1, x2 - x1, y2 - y1])
                scores_for_nms.append(confidence)
                class_ids.append(int(class_id))

        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_for_nms,
            scores=scores_for_nms,
            score_threshold=self.conf_thresh,
            nms_threshold=0.45
        )

        for i in indices:
            i = int(i)
            x, y, w, h = boxes_for_nms[i]
            results.append({
                "class_id": class_ids[i],
                "confidence": round(scores_for_nms[i], 4),
                "bbox": [x, y, x + w, y + h]
            })

        json_output = json.dumps({
            "inference_time_ms": float(round(infer_time, 2)),
            "fps": float(round(fps, 2)),
            "detections": results
        }, indent=4)

        # Force bbox
        json_output = re.sub(
            r'"bbox": \[\s*([^\]]*?)\s*\]',
            lambda m: '"bbox": [' + ', '.join(part.strip() for part in m.group(1).split(',')) + ']',
            json_output,
            flags=re.DOTALL,
        )
        
        return json_output

if __name__ == "__main__":
    MODEL_PATH = "models/best_int8.tflite"
    IMAGE_DIR  = "test-images"
    OUTPUT_CSV = "results.csv"

    SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
    
    try:
        engine = YoloTfliteEngine(model_path=MODEL_PATH, conf_thresh=0.5)
        
        image_files = sorted([
            f for f in os.listdir(IMAGE_DIR)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
        ])
        print(f"[INFO] Found {len(image_files)} images in '{IMAGE_DIR}'")

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "image", "inference_time_ms", "fps",
                "detection_index", "class_id", "confidence",
                "x1", "y1", "x2", "y2"
            ])

            for filename in image_files:
                img_path = os.path.join(IMAGE_DIR, filename)
                
                print(f"[INFO] Processing: {filename}")
                start_e2e = time.time()
                result_json = engine.infer(img_path=img_path)
                e2e_ms = (time.time() - start_e2e) * 1000
                print(f"[INFO] End-to-end: {e2e_ms:.2f} ms ({1000 / e2e_ms:.2f} FPS)")
                result = json.loads(result_json)

                detections = result["detections"]
                infer_ms   = result["inference_time_ms"]
                fps        = result["fps"]

                if not detections:
                    writer.writerow([filename, infer_ms, fps, -1, "", "", "", "", "", ""])
                else:
                    for idx, det in enumerate(detections):
                        x1, y1, x2, y2 = det["bbox"]
                        writer.writerow([
                            filename, infer_ms, fps,
                            idx, det["class_id"], det["confidence"],
                            x1, y1, x2, y2
                        ])
            
                print("\n[RESULT] INFERENCE RESULTS (JSON):")
                print(result_json)
        print(f"\n[INFO] Save results at '{OUTPUT_CSV}'")
        
    except Exception as e:
        print(f"\n[EXCEPTION] Đã xảy ra lỗi: {e}")