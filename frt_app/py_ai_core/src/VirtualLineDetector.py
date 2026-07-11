"""
VirtualLineDetector.py - Detects fridge edge as a virtual boundary line for tracking
Version: 1.0
Purpose:
    Uses Hough Transform to automatically detect the longest straight line
    in the edge areas of the frame (1/3 of frame margins) when the door opens.
"""

import cv2
import numpy as np
from loguru import logger
from typing import Dict, Optional

class VirtualLineDetector:
    def __init__(self, edge_margin_ratio: float = 0.33):
        self.edge_margin_ratio = edge_margin_ratio
        
    def detect_virtual_line(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Detect the virtual line from the frame.
        
        Args:
            frame: Input image frame in BGR format
            
        Returns:
            Dict containing line information:
                - type: 'horizontal' or 'vertical'
                - pos: Coordinate position (y for horizontal, x for vertical)
                - start: Start of line segment
                - end: End of line segment
            Or None if no valid line found.
        """
        try:
            # 1. Grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 2. Gaussian Blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 3. Edge Detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # 4. Hough Line Transform
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=50, maxLineGap=10)
            
            if lines is None:
                return None
                
            height, width = frame.shape[:2]
            best_line_info = None
            max_length = 0
            
            for line in lines:
                x1, y1, x2, y2 = line[0]
                
                # Calculate length
                length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                # Identify if line is horizontal or vertical (filter diagonal)
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                
                # Use a small threshold (e.g. slope 0.2 ~ 11 degrees) to allow slight tilt
                is_horizontal = dy < 0.2 * dx
                is_vertical = dx < 0.2 * dy
                
                if not (is_horizontal or is_vertical):
                    continue
                    
                in_edge_area = False
                line_info = {}
                
                if is_horizontal:
                    y_avg = (y1 + y2) / 2
                    # Check top 1/3 or bottom 1/3
                    if y_avg < height * self.edge_margin_ratio or y_avg > height * (1.0 - self.edge_margin_ratio):
                        in_edge_area = True
                        line_info = {
                            'type': 'horizontal',
                            'pos': y_avg,
                            'start': min(x1, x2),
                            'end': max(x1, x2)
                        }
                elif is_vertical:
                    x_avg = (x1 + x2) / 2
                    # Check left 1/3 or right 1/3
                    if x_avg < width * self.edge_margin_ratio or x_avg > width * (1.0 - self.edge_margin_ratio):
                        in_edge_area = True
                        line_info = {
                            'type': 'vertical',
                            'pos': x_avg,
                            'start': min(y1, y2),
                            'end': max(y1, y2)
                        }
                        
                if in_edge_area and length > max_length:
                    max_length = length
                    best_line_info = line_info
                    
            if best_line_info:
                logger.info(f"Virtual Line detected: {best_line_info['type']} at pos {int(best_line_info['pos'])} (length: {int(max_length)})")
                return best_line_info
                
            return None
        except Exception as e:
            logger.error(f"Error detecting virtual line: {e}")
            return None

if __name__ == "__main__":
    detector = VirtualLineDetector()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.line(dummy_frame, (50, 50), (50, 400), (255, 255, 255), 2)
    res = detector.detect_virtual_line(dummy_frame)
    print("Test result:", res)
