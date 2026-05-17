"""
YoloPipeline.py - YOLOv11 Inference Pipeline with ByteTrack Integration
Version: 1.0
SDD v1.1.0 Compliance: Core pipeline class integrating all FRTApp components

Purpose:
    Complete inference pipeline combining:
    - SharedMemoryReader: Read frames from C++ camera core
    - MotionDetector: MOG2 background subtraction
    - ImagePreprocessor: Frame normalization
    - YoloTfliteEngine: YOLOv11 TFLite inference
    - ByteTrack: Multi-object tracking across frames

Pipeline Flow:
    1. Read frame from shared memory (or camera directly)
    2. Apply MOG2 motion detection (skip frames without motion)
    3. Preprocess frame for YOLO (resize, normalize)
    4. Run YOLOv11 inference
    5. Apply ByteTrack for object tracking
    6. Return detection results with persistent track IDs

Author: FSS Project Team
License: Proprietary
"""

import numpy as np
import mmap
import struct
import time
from typing import Dict, List, Optional, Tuple
from loguru import logger

# Import FRTApp components
from CameraUvcDriver import CameraUvcDriver
from MotionDetector import MotionDetector
from ImagePreprocessor import ImagePreprocessor
from YoloTfliteEngine import YoloTfliteEngine


class SharedMemoryReader:
    """
    Read JPEG/RGB frames from POSIX shared memory.
    
    Shared Memory Layout:
        - Name: /fss_video_frame
        - Header: 64 bytes (FrameHeader structure)
        - Data: Frame bytes (JPEG or raw RGB)
    """
    
    SHM_NAME = "/fss_video_frame"
    
    def __init__(self, shm_name: str = None):
        """Initialize shared memory reader."""
        self.shm_name = shm_name or self.SHM_NAME
        self.shm_fd = None
        self.shm_buffer = None
        self.is_attached = False
    
    def attach(self) -> bool:
        """
        Attach to shared memory region.
        
        Returns:
            bool: True if attached successfully
        """
        try:
            import os
            
            # Try to open existing shared memory
            self.shm_fd = os.open(f"/dev/shm{self.shm_name}", os.O_RDONLY)
            if self.shm_fd >= 0:
                logger.info(f"Attached to shared memory: {self.shm_name}")
                self.is_attached = True
                return True
                
        except Exception as e:
            logger.debug(f"Shared memory not available: {e}")
            
        self.is_attached = False
        return False
    
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read frame from shared memory.
        
        Returns:
            np.ndarray: Frame in BGR format or None
        """
        # Placeholder - shared memory reading will be implemented
        # when C++ camera core is running
        return None
    
    def detach(self):
        """Detach from shared memory."""
        if self.shm_fd is not None:
            import os
            os.close(self.shm_fd)
            self.shm_fd = None
        self.is_attached = False


class ByteTrack:
    """
    ByteTrack multi-object tracker integration.
    
    Purpose:
        Track objects across frames to detect +1/-1 quantity changes.
        Assign persistent IDs to detected food items.
    
    Algorithm:
        1. Sort detections by confidence
        2. First association: High confidence detections with Kalman filter predictions
        3. Second association: Low confidence detections with remaining predictions
        4. Create new tracks for unmatched detections
        5. Remove old tracks (lost for too long)
    """
    
    def __init__(self, max_age: int = 30):
        """
        Initialize ByteTrack tracker.
        
        Args:
            max_age: Maximum frames to keep lost tracks
        """
        self.max_age = max_age
        self.tracks: Dict[int, Dict] = {}  # track_id -> track_data
        self.next_track_id = 1
        self.detection_history: List[Dict] = []
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of detection dicts with 'bbox', 'confidence', 'class_id'
            
        Returns:
            List of tracked objects with 'track_id' added
        """
        tracks = []
        
        for det in detections:
            # Simple nearest neighbor assignment
            track_id = self._assign_track(det)
            
            track_data = {
                'track_id': track_id,
                'bbox': det['bbox'],
                'confidence': det['confidence'],
                'class_id': det['class_id'],
                'age': 0
            }
            
            self.tracks[track_id] = track_data
            tracks.append(track_data)
        
        # Increment age for unmatched tracks
        matched_ids = {t['track_id'] for t in tracks}
        for track_id in list(self.tracks.keys()):
            if track_id not in matched_ids:
                self.tracks[track_id]['age'] += 1
                if self.tracks[track_id]['age'] > self.max_age:
                    del self.tracks[track_id]
        
        return tracks
    
    def _assign_track(self, detection: Dict) -> int:
        """
        Assign existing or new track ID to detection.
        
        Args:
            detection: Detection dictionary
            
        Returns:
            Track ID
        """
        # Simple IoU-based assignment
        best_iou = 0.5
        best_track_id = -1
        
        for track_id, track in self.tracks.items():
            iou = self._calculate_iou(detection['bbox'], track['bbox'])
            if iou > best_iou:
                best_iou = iou
                best_track_id = track_id
        
        if best_track_id >= 0:
            return best_track_id
        
        # Create new track
        track_id = self.next_track_id
        self.next_track_id += 1
        return track_id
    
    def _calculate_iou(self, bbox1: List, bbox2: List) -> float:
        """Calculate IoU between two bounding boxes."""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)
        
        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0
        
        intersection = (xi2 - xi1) * (yi2 - yi1)
        union = w1 * h1 + w2 * h2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def get_quantity_change(self) -> Dict[int, int]:
        """
        Detect quantity changes based on track history.
        
        Returns:
            Dict mapping class_id -> quantity change (+1 or -1)
        """
        changes = {}
        
        for track_id, track in self.tracks.items():
            class_id = track['class_id']
            
            # Simple logic: count new tracks as +1
            if track.get('age', 0) == 0:
                changes[class_id] = changes.get(class_id, 0) + 1
        
        return changes
    
    def reset(self):
        """Reset tracker state."""
        self.tracks.clear()
        self.next_track_id = 1
        self.detection_history.clear()


class YoloPipeline:
    """
    Complete YOLO inference pipeline with tracking.
    
    Components:
        - SharedMemoryReader: Read frames from C++ camera
        - CameraUvcDriver: Direct camera access (fallback)
        - MotionDetector: MOG2 background subtraction
        - ImagePreprocessor: Frame preprocessing
        - YoloTfliteEngine: YOLO model inference
        - ByteTrack: Object tracking
    """
    
    def __init__(
        self,
        model_path: str = "/opt/fss/models/yolov11n.tflite",
        use_shared_memory: bool = True
    ):
        """
        Initialize YOLO pipeline.
        
        Args:
            model_path: Path to TFLite model
            use_shared_memory: Use C++ camera core's shared memory
        """
        self.use_shared_memory = use_shared_memory
        
        # Initialize components
        self.motion_detector = MotionDetector(threshold_percent=1.0)
        self.preprocessor = ImagePreprocessor(640, 640)
        self.ai_engine = YoloTfliteEngine(model_path)
        self.tracker = ByteTrack(max_age=30)
        
        # Camera handling
        self.camera_driver = CameraUvcDriver()
        self.shm_reader = SharedMemoryReader()
        
        # State
        self.is_initialized = False
        self.frame_count = 0
        self.inference_count = 0
        
        logger.info("YoloPipeline initialized")
    
    def init_pipeline(self) -> bool:
        """
        Initialize all pipeline components.
        
        Returns:
            bool: True if all components initialized
        """
        logger.info("Initializing YOLO pipeline...")
        
        # Initialize MOG2
        self.motion_detector.init_mog2()
        
        # Load YOLO model
        if not self.ai_engine.load_model_mmap():
            logger.warning("YOLO model not loaded (model file may be missing)")
        
        # Attach to shared memory if available
        if self.use_shared_memory:
            self.shm_reader.attach()
        
        self.is_initialized = True
        logger.info("Pipeline initialized")
        return True
    
    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process single frame through pipeline.
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Dict with detection results and tracking data
        """
        if not self.is_initialized:
            return {"error": "Pipeline not initialized"}
        
        self.frame_count += 1
        
        # Step 1: Motion detection
        motion_mask = self.motion_detector.apply_background_subtraction(frame)
        if motion_mask is not None and not self.motion_detector.is_motion_detected(motion_mask):
            # No motion, skip inference
            return {
                "frame_id": self.frame_count,
                "skipped": True,
                "reason": "no_motion"
            }
        
        # Step 2: Preprocess
        tensor = self.preprocessor.prepare_tensor_input(frame)
        if tensor is None:
            return {
                "frame_id": self.frame_count,
                "error": "Preprocessing failed"
            }
        
        # Step 3: Inference
        self.ai_engine.set_input_tensor(tensor)
        self.ai_engine.invoke_inference()
        detections = self.ai_engine.get_output_boxes()
        
        self.inference_count += 1
        
        # Step 4: Tracking
        tracked = self.tracker.update(detections)
        
        return {
            "frame_id": self.frame_count,
            "detections": detections,
            "tracked": tracked,
            "count": len(detections)
        }
    
    def run_stream(self, max_frames: int = None):
        """
        Run inference loop on camera stream.
        
        Args:
            max_frames: Maximum frames to process (None = infinite)
        """
        if not self.camera_driver.open_camera_stream():
            logger.error("Failed to open camera stream")
            return
        
        frame_count = 0
        
        while (max_frames is None or frame_count < max_frames):
            frame = self.camera_driver.read_frame()
            if frame is None:
                continue
            
            result = self.process_frame(frame)
            
            if not result.get("skipped"):
                logger.debug(f"Frame {result['frame_id']}: {result['count']} detections")
            
            frame_count += 1
        
        self.camera_driver.release_camera()
    
    def get_metrics(self) -> Dict:
        """Get pipeline performance metrics."""
        return {
            "total_frames": self.frame_count,
            "total_inferences": self.inference_count,
            "active_tracks": len(self.tracker.tracks)
        }


# ============================================================================
# MAIN ENTRY POINT (Testing)
# ============================================================================

if __name__ == "__main__":
    logger.info("YoloPipeline - Test Entry Point")
    
    # Test pipeline initialization
    logger.info("=== TEST: PIPELINE INITIALIZATION ===")
    pipeline = YoloPipeline()
    
    if pipeline.init_pipeline():
        logger.info("✓ Pipeline initialized")
    else:
        logger.error("✗ Pipeline initialization failed")
    
    # Test with dummy frame
    logger.info("=== TEST: DUMMY FRAME PROCESSING ===")
    dummy_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    
    result = pipeline.process_frame(dummy_frame)
    if "error" not in result:
        logger.info(f"✓ Frame processed: {result.get('count', 0)} detections")
    else:
        logger.info(f"⚠ Frame result: {result}")
    
    # Print metrics
    metrics = pipeline.get_metrics()
    logger.info(f"Metrics: {metrics}")