import os
import cv2
import argparse
import glob
import numpy as np
import time

def process_video(input_path, output_path, history, var_threshold, min_area):
    """
    Chạy MOG2 trên input_path với các tham số cho trước và lưu kết quả vào output_path.
    """
    is_dir = os.path.isdir(input_path)
    if is_dir:
        image_files = sorted(glob.glob(os.path.join(input_path, "*.jpg")) + 
                             glob.glob(os.path.join(input_path, "*.png")))
        if not image_files:
            print(f"Không tìm thấy ảnh trong thư mục {input_path}")
            return False
        # Đọc frame đầu tiên để lấy kích thước
        first_frame = cv2.imread(image_files[0])
        height, width = first_frame.shape[:2]
        fps = 10.0 # Mặc định fps cho ảnh tĩnh
    else:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print(f"Không thể mở video {input_path}")
            return False
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            fps = 25.0

    # Khởi tạo VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Khởi tạo MOG2
    backSub = cv2.createBackgroundSubtractorMOG2(history=history, varThreshold=var_threshold, detectShadows=True)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    frame_count = 0
    start_time = time.time()

    while True:
        if is_dir:
            if frame_count >= len(image_files):
                break
            frame = cv2.imread(image_files[frame_count])
        else:
            ret, frame = cap.read()
            if not ret:
                break

        # Cập nhật background model
        fgMask = backSub.apply(frame)

        # Loại bỏ bóng râm (shadows thường có giá trị pixel 127)
        # Chỉ giữ lại phần foreground thực sự (giá trị 255)
        _, fgMask = cv2.threshold(fgMask, 200, 255, cv2.THRESH_BINARY)

        # Morphological operations để giảm nhiễu
        # Opening: xóa nhiễu nhỏ (noise)
        fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_OPEN, kernel, iterations=1)
        # Closing: lấp đầy lỗ hổng trong object
        fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Tìm các contours (đường viền của vật thể di chuyển)
        contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Vẽ Bounding Box
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, "Motion", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Thêm thông tin tham số vào video để dễ theo dõi
        info_text = f"H:{history} V:{var_threshold} A:{min_area}"
        cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        out.write(frame)
        frame_count += 1

    if not is_dir:
        cap.release()
    out.release()
    
    elapsed = time.time() - start_time
    print(f"[Done] {output_path} - {frame_count} frames in {elapsed:.2f}s")
    return True

def generate_html_report(output_dir, results):
    """
    Tạo file HTML hiển thị dạng lưới các video kết quả để dễ so sánh.
    """
    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<html><head><title>MOG2 Grid Search Results</title>\n")
        f.write("<style>\n")
        f.write("body { font-family: Arial, sans-serif; background-color: #f4f4f9; padding: 20px; }\n")
        f.write(".grid-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }\n")
        f.write(".grid-item { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }\n")
        f.write("video { width: 100%; height: auto; border-radius: 5px; }\n")
        f.write("h3 { margin-top: 0; font-size: 16px; color: #333; }\n")
        f.write("</style></head><body>\n")
        f.write("<h1>MOG2 Grid Search Results</h1>\n")
        f.write("<div class='grid-container'>\n")
        
        for res in results:
            video_filename = os.path.basename(res['file'])
            f.write("  <div class='grid-item'>\n")
            f.write(f"    <h3>History: {res['history']} | Var: {res['var']} | Area: {res['area']}</h3>\n")
            f.write(f"    <video controls loop muted>\n")
            f.write(f"      <source src='{video_filename}' type='video/mp4'>\n")
            f.write("      Trình duyệt của bạn không hỗ trợ thẻ video.\n")
            f.write("    </video>\n")
            f.write("  </div>\n")
            
        f.write("</div>\n</body></html>\n")
    print(f"\n[+] Báo cáo HTML đã được tạo: {html_path}")
    print("Mở file này bằng trình duyệt để so sánh kết quả.")

def main():
    parser = argparse.ArgumentParser(description="Grid Search tham số cho MOG2")
    parser.add_argument("--input", required=True, help="Đường dẫn đến file video hoặc thư mục chứa ảnh tĩnh")
    parser.add_argument("--out_dir", default="results/mog2_gridsearch", help="Thư mục lưu kết quả")
    
    # Cho phép người dùng ghi đè các dải tham số nếu muốn
    parser.add_argument("--histories", type=int, nargs="+", default=[100, 500], help="Danh sách các giá trị history (mặc định: 100 500)")
    parser.add_argument("--var_thresholds", type=int, nargs="+", default=[16, 50, 100], help="Danh sách các giá trị varThreshold (mặc định: 16 50 100)")
    parser.add_argument("--min_areas", type=int, nargs="+", default=[500, 1000], help="Danh sách các giá trị minArea (mặc định: 500 1000)")
    
    args = parser.parse_args()

    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)

    results = []
    total_combinations = len(args.histories) * len(args.var_thresholds) * len(args.min_areas)
    print(f"Bắt đầu Grid Search MOG2 với {total_combinations} tổ hợp tham số...")
    
    count = 1
    for h in args.histories:
        for v in args.var_thresholds:
            for a in args.min_areas:
                filename = f"result_h{h}_v{v}_a{a}.mp4"
                output_path = os.path.join(args.out_dir, filename)
                
                print(f"[{count}/{total_combinations}] Đang chạy: history={h}, varThreshold={v}, minArea={a}")
                success = process_video(args.input, output_path, h, v, a)
                
                if success:
                    results.append({
                        'file': output_path,
                        'history': h,
                        'var': v,
                        'area': a
                    })
                count += 1
                
    if results:
        generate_html_report(args.out_dir, results)

if __name__ == "__main__":
    main()
