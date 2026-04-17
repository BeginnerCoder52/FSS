import os
import csv
import cv2
import numpy as np
import json
import re
import time
import argparse
from tflite_runtime.interpreter import Interpreter

class YoloTfliteEngine:
    def __init__(self, model_path, conf_thresh=0.5, debug=False, num_threads=2):
        """Khởi tạo Engine suy luận TFLite"""
        self.debug = debug
        self.num_threads = num_threads
        print(f"[INFO] Đang tải mô hình từ: {model_path}...")
        print(f"[INFO] TFLite num_threads={self.num_threads}")
        self.interpreter = Interpreter(
            model_path=model_path,
            num_threads=self.num_threads
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

    def set_debug(self, enabled):
        self.debug = enabled

    def _debug(self, message):
        if self.debug:
            print(message)

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
        self._debug(f"[DEBUG] squeezed shape: {squeezed.shape} -> predictions shape: {predictions.shape}")

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
                self._debug(f"[DEBUG] raw xc={xc:.4f} yc={yc:.4f} w={w:.4f} h={h:.4f}")
                
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


def parse_benchmark_threads(raw_text):
    values = []
    for part in raw_text.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError as exc:
            raise ValueError(f"num_threads khong hop le: '{item}'") from exc
        if value <= 0:
            raise ValueError("num_threads phai > 0")
        values.append(value)

    if not values:
        raise ValueError("--benchmark-num-threads dang rong")

    unique_values = []
    seen = set()
    for value in values:
        if value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values


def compute_iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def yolo_to_xyxy(x_center, y_center, width, height, img_w, img_h):
    x1 = (x_center - width / 2.0) * img_w
    y1 = (y_center - height / 2.0) * img_h
    x2 = (x_center + width / 2.0) * img_w
    y2 = (y_center + height / 2.0) * img_h

    x1 = min(max(0.0, x1), float(img_w))
    y1 = min(max(0.0, y1), float(img_h))
    x2 = min(max(0.0, x2), float(img_w))
    y2 = min(max(0.0, y2), float(img_h))
    return [x1, y1, x2, y2]


def load_yolo_labels(label_path, img_w, img_h):
    gt_boxes = []
    if not os.path.isfile(label_path):
        return gt_boxes

    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue

            try:
                class_id = int(float(parts[0]))
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
            except ValueError:
                continue

            bbox = yolo_to_xyxy(x_center, y_center, width, height, img_w, img_h)
            gt_boxes.append({"class_id": class_id, "bbox": bbox})

    return gt_boxes


def compute_ap(recalls, precisions):
    if len(recalls) == 0:
        return 0.0

    mrec = np.concatenate(([0.0], recalls, [1.0]))
    mpre = np.concatenate(([0.0], precisions, [0.0]))

    for i in range(mpre.size - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])

    indices = np.where(mrec[1:] != mrec[:-1])[0]
    ap = np.sum((mrec[indices + 1] - mrec[indices]) * mpre[indices + 1])
    return float(ap)


def evaluate_map50(predictions_by_image, gt_by_image, iou_thresh=0.5):
    per_class = {}

    for image_name, gt_items in gt_by_image.items():
        for gt in gt_items:
            cls = gt["class_id"]
            per_class.setdefault(cls, {
                "num_gt": 0,
                "scores": [],
                "tp": [],
                "fp": [],
                "num_pred": 0,
            })
            per_class[cls]["num_gt"] += 1

    gt_index = {}
    for image_name, gt_items in gt_by_image.items():
        gt_index[image_name] = {}
        for gt in gt_items:
            cls = gt["class_id"]
            gt_index[image_name].setdefault(cls, []).append({
                "bbox": gt["bbox"],
                "matched": False,
            })

    all_predictions = []
    for image_name, pred_items in predictions_by_image.items():
        for pred in pred_items:
            cls = int(pred["class_id"])
            conf = float(pred["confidence"])
            bbox = [float(v) for v in pred["bbox"]]
            all_predictions.append((conf, image_name, cls, bbox))

            per_class.setdefault(cls, {
                "num_gt": 0,
                "scores": [],
                "tp": [],
                "fp": [],
                "num_pred": 0,
            })
            per_class[cls]["num_pred"] += 1

    all_predictions.sort(key=lambda x: x[0], reverse=True)

    total_tp = 0
    total_fp = 0

    for conf, image_name, cls, pred_bbox in all_predictions:
        cls_stats = per_class[cls]
        cls_stats["scores"].append(conf)

        best_iou = 0.0
        best_gt_idx = -1
        candidates = gt_index.get(image_name, {}).get(cls, [])

        for idx, gt in enumerate(candidates):
            if gt["matched"]:
                continue
            iou = compute_iou(pred_bbox, gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = idx

        if best_gt_idx >= 0 and best_iou >= iou_thresh:
            candidates[best_gt_idx]["matched"] = True
            cls_stats["tp"].append(1)
            cls_stats["fp"].append(0)
            total_tp += 1
        else:
            cls_stats["tp"].append(0)
            cls_stats["fp"].append(1)
            total_fp += 1

    total_gt = sum(stats["num_gt"] for stats in per_class.values())
    precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
    recall = (total_tp / total_gt) if total_gt > 0 else 0.0

    ap_values = []
    per_class_report = []
    for cls in sorted(per_class.keys()):
        stats = per_class[cls]
        num_gt = stats["num_gt"]
        tp = np.array(stats["tp"], dtype=np.float32)
        fp = np.array(stats["fp"], dtype=np.float32)

        if len(tp) > 0:
            cum_tp = np.cumsum(tp)
            cum_fp = np.cumsum(fp)
            precisions = cum_tp / np.maximum(cum_tp + cum_fp, 1e-12)
            recalls = cum_tp / max(float(num_gt), 1e-12)
        else:
            precisions = np.array([], dtype=np.float32)
            recalls = np.array([], dtype=np.float32)

        ap50 = compute_ap(recalls, precisions) if num_gt > 0 else 0.0
        if num_gt > 0:
            ap_values.append(ap50)

        cls_precision = float(precisions[-1]) if len(precisions) > 0 else 0.0
        cls_recall = float(recalls[-1]) if len(recalls) > 0 else 0.0

        per_class_report.append({
            "class_id": cls,
            "num_gt": int(num_gt),
            "num_pred": int(stats["num_pred"]),
            "tp": int(np.sum(tp)) if len(tp) > 0 else 0,
            "fp": int(np.sum(fp)) if len(fp) > 0 else 0,
            "precision": cls_precision,
            "recall": cls_recall,
            "ap50": float(ap50),
        })

    map50 = float(np.mean(ap_values)) if ap_values else 0.0

    return {
        "iou_threshold": float(iou_thresh),
        "total_gt": int(total_gt),
        "total_pred": int(total_tp + total_fp),
        "total_tp": int(total_tp),
        "total_fp": int(total_fp),
        "precision": float(precision),
        "recall": float(recall),
        "map50": map50,
        "per_class": per_class_report,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch test inference cho model TFLite")
    parser.add_argument("--model", default="models/model_int8.tflite", help="Đường dẫn model TFLite")
    parser.add_argument("--image-dir", default="test-images", help="Thư mục chứa ảnh test")
    parser.add_argument("--labels-dir", default="", help="Thư mục chứa label YOLO (.txt) để eval")
    parser.add_argument("--output-dir", default="results", help="Thư mục lưu kết quả theo từng lần chạy")
    parser.add_argument("--conf", type=float, default=0.5, help="Ngưỡng confidence")
    parser.add_argument("--eval-iou", type=float, default=0.5, help="Ngưỡng IoU để tính TP/FP (mặc định mAP50)")
    parser.add_argument("--num-threads", type=int, default=2, help="Số luồng TFLite cho 1 lần chạy")
    parser.add_argument(
        "--benchmark-num-threads",
        default="",
        help="Danh sách num_threads để benchmark, ví dụ: 1,2,4",
    )
    parser.add_argument("--debug", action="store_true", help="Bật debug log")
    parser.add_argument(
        "--auto-disable-debug",
        action="store_true",
        help="Tự tắt debug mode sau ảnh đầu tiên",
    )
    args = parser.parse_args()

    SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
    
    try:
        if args.num_threads <= 0:
            raise ValueError("--num-threads phai > 0")
        if not (0.0 < args.eval_iou <= 1.0):
            raise ValueError("--eval-iou phai trong khoang (0, 1]")

        if args.benchmark_num_threads.strip():
            thread_values = parse_benchmark_threads(args.benchmark_num_threads)
        else:
            thread_values = [args.num_threads]

        image_dir = args.image_dir
        direct_images = []
        if os.path.isdir(image_dir):
            direct_images = [
                f for f in os.listdir(image_dir)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
            ]
        nested_image_dir = os.path.join(args.image_dir, "images")
        if not direct_images and os.path.isdir(nested_image_dir):
            image_dir = nested_image_dir

        labels_dir = args.labels_dir.strip()
        if not labels_dir:
            labels_from_dataset_root = os.path.join(args.image_dir, "labels")
            labels_from_image_sibling = os.path.join(os.path.dirname(image_dir), "labels")
            if os.path.isdir(labels_from_dataset_root):
                labels_dir = labels_from_dataset_root
            elif os.path.isdir(labels_from_image_sibling):
                labels_dir = labels_from_image_sibling

        eval_enabled = os.path.isdir(labels_dir)
        if eval_enabled:
            print(f"[INFO] Eval mode ON, labels dir: '{labels_dir}'")
        else:
            print("[WARN] Khong tim thay labels dir hop le. Chi benchmark speed, bo qua eval metrics.")
        
        image_files = sorted([
            f for f in os.listdir(image_dir)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
        ])
        total_images = len(image_files)
        print(f"[INFO] Found {total_images} images in '{image_dir}'")

        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(args.output_dir, f"run_{run_id}")
        os.makedirs(run_dir, exist_ok=True)
        model_name = os.path.splitext(os.path.basename(args.model))[0]
        safe_model_name = re.sub(r"[^A-Za-z0-9._-]+", "_", model_name)
        benchmark_rows = []

        for num_threads in thread_values:
            print(f"\n[INFO] Start inference with num_threads={num_threads}")
            engine = YoloTfliteEngine(
                model_path=args.model,
                conf_thresh=args.conf,
                debug=args.debug,
                num_threads=num_threads,
            )
            output_csv = os.path.join(run_dir, f"results_{safe_model_name}_t{num_threads}.csv")
            eval_per_class_csv = os.path.join(run_dir, f"eval_per_class_{safe_model_name}_t{num_threads}.csv")
            infer_times = []
            batch_start_time = time.time()
            predictions_by_image = {}
            gt_by_image = {}

            with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "image", "inference_time_ms", "fps",
                    "detection_index", "class_id", "confidence",
                    "x1", "y1", "x2", "y2"
                ])

                for idx_file, filename in enumerate(image_files, start=1):
                    img_path = os.path.join(image_dir, filename)
                    result_json = engine.infer(img_path=img_path)
                    result = json.loads(result_json)

                    detections = result["detections"]
                    infer_ms   = float(result["inference_time_ms"])
                    fps        = result["fps"]
                    infer_times.append(infer_ms)

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

                    if eval_enabled:
                        predictions_by_image[filename] = detections
                        image = cv2.imread(img_path)
                        if image is None:
                            gt_by_image[filename] = []
                        else:
                            img_h, img_w = image.shape[:2]
                            label_name = os.path.splitext(filename)[0] + ".txt"
                            label_path = os.path.join(labels_dir, label_name)
                            gt_by_image[filename] = load_yolo_labels(label_path, img_w, img_h)

                    if args.auto_disable_debug and idx_file == 1 and engine.debug:
                        engine.set_debug(False)
                        print(f"[INFO][t={num_threads}] Debug mode auto-disabled after first image")

                    print(f"[INFO][t={num_threads}] Da suy luan: {idx_file}/{total_images} anh")

            total_wall_time_s = time.time() - batch_start_time
            avg_infer_ms = (sum(infer_times) / len(infer_times)) if infer_times else 0.0
            avg_fps = (1000.0 / avg_infer_ms) if avg_infer_ms > 0 else 0.0
            eval_result = None
            if eval_enabled:
                eval_result = evaluate_map50(
                    predictions_by_image=predictions_by_image,
                    gt_by_image=gt_by_image,
                    iou_thresh=args.eval_iou,
                )

                with open(eval_per_class_csv, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([
                        "class_id",
                        "num_gt",
                        "num_pred",
                        "tp",
                        "fp",
                        "precision",
                        "recall",
                        "ap50",
                    ])
                    for row in eval_result["per_class"]:
                        writer.writerow([
                            row["class_id"],
                            row["num_gt"],
                            row["num_pred"],
                            row["tp"],
                            row["fp"],
                            round(row["precision"], 6),
                            round(row["recall"], 6),
                            round(row["ap50"], 6),
                        ])

                print(
                    f"[EVAL][t={num_threads}] "
                    f"Precision={eval_result['precision']:.4f} "
                    f"Recall={eval_result['recall']:.4f} "
                    f"mAP50={eval_result['map50']:.4f}"
                )
                print(f"[INFO] Save per-class eval at '{eval_per_class_csv}'")

            benchmark_rows.append({
                "num_threads": num_threads,
                "images": total_images,
                "avg_inference_time_ms": round(avg_infer_ms, 2),
                "avg_fps": round(avg_fps, 2),
                "total_wall_time_s": round(total_wall_time_s, 2),
                "result_csv": output_csv,
                "precision": round(eval_result["precision"], 6) if eval_result else "",
                "recall": round(eval_result["recall"], 6) if eval_result else "",
                "map50": round(eval_result["map50"], 6) if eval_result else "",
                "eval_per_class_csv": eval_per_class_csv if eval_result else "",
            })
            print(f"[INFO] Save results at '{output_csv}'")

        if benchmark_rows:
            summary_csv = os.path.join(run_dir, f"benchmark_summary_{safe_model_name}.csv")
            baseline = benchmark_rows[0]["avg_inference_time_ms"]
            with open(summary_csv, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "num_threads",
                    "images",
                    "avg_inference_time_ms",
                    "avg_fps",
                    "precision",
                    "recall",
                    "map50",
                    "delta_ms_vs_first",
                    "delta_pct_vs_first",
                    "total_wall_time_s",
                    "result_csv",
                    "eval_per_class_csv",
                ])
                for row in benchmark_rows:
                    delta_ms = row["avg_inference_time_ms"] - baseline
                    delta_pct = (delta_ms / baseline * 100.0) if baseline > 0 else 0.0
                    writer.writerow([
                        row["num_threads"],
                        row["images"],
                        row["avg_inference_time_ms"],
                        row["avg_fps"],
                        row["precision"],
                        row["recall"],
                        row["map50"],
                        round(delta_ms, 2),
                        round(delta_pct, 2),
                        row["total_wall_time_s"],
                        row["result_csv"],
                        row["eval_per_class_csv"],
                    ])

            print(f"\n[INFO] Save benchmark summary at '{summary_csv}'")
            print("[INFO] So sanh nhanh theo avg_inference_time_ms (so voi cau hinh dau tien):")
            for row in benchmark_rows:
                delta_ms = row["avg_inference_time_ms"] - baseline
                delta_pct = (delta_ms / baseline * 100.0) if baseline > 0 else 0.0
                print(
                    f"  - t={row['num_threads']}: {row['avg_inference_time_ms']:.2f} ms "
                    f"({delta_ms:+.2f} ms, {delta_pct:+.2f}%)"
                )
        
    except Exception as e:
        print(f"\n[EXCEPTION] Đã xảy ra lỗi: {e}")
