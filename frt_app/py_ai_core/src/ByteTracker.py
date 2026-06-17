"""
ByteTracker.py - ByteTrack Algorithm implementation with Line Crossing Logic
Version: 1.0
SDD v1.1.0 Compliance: Replaces naive tracker to handle occlusion and exact entry/exit crossing.
"""

import numpy as np
import scipy.linalg
from scipy.optimize import linear_sum_assignment
from loguru import logger
from typing import List, Dict, Tuple, Optional

# Food class name lookup (standalone fallback; overridden by FrtMain if available)
FOOD_CLASS_NAMES = {
    0: "apple", 1: "carrot", 2: "egg", 3: "lemon", 4: "tomato",
    5: "banana", 6: "orange", 7: "bottle", 8: "cup", 9: "bowl",
    10: "cake", 11: "donut", 12: "sandwich", 13: "broccoli",
    14: "pizza", 15: "hot dog", 16: "milk", 17: "juice",
    18: "yogurt", 19: "cheese", 20: "meat", 21: "fish",
    22: "bread", 23: "rice", 24: "noodles", 25: "cookie",
}


def _get_food_name(class_id: int) -> str:
    """Resolve numeric class_id to human-readable food name."""
    return FOOD_CLASS_NAMES.get(class_id, "food_class_{}".format(class_id))

class KalmanFilter:
    """
    A simple Kalman filter for tracking bounding boxes in image space.
    The 8-dimensional state space is
        x, y, a, h, vx, vy, va, vh
    contains the bounding box center position (x, y), aspect ratio a, height h,
    and their respective velocities.
    """

    def __init__(self):
        ndim, dt = 4, 1.

        # Create Kalman filter model matrices.
        self._motion_mat = np.eye(2 * ndim, 2 * ndim)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = dt
        self._update_mat = np.eye(ndim, 2 * ndim)

        # Motion and observation uncertainty are chosen relative to the current
        # state estimate. These weights control the amount of uncertainty in
        # the model.
        self._std_weight_position = 1. / 20
        self._std_weight_velocity = 1. / 160

    def initiate(self, measurement):
        """Create track from unassociated measurement."""
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        std = [
            2 * self._std_weight_position * measurement[3],
            2 * self._std_weight_position * measurement[3],
            1e-2,
            2 * self._std_weight_position * measurement[3],
            10 * self._std_weight_velocity * measurement[3],
            10 * self._std_weight_velocity * measurement[3],
            1e-5,
            10 * self._std_weight_velocity * measurement[3]]
        covariance = np.diag(np.square(std))
        return mean, covariance

    def predict(self, mean, covariance):
        """Run Kalman filter prediction step."""
        std_pos = [
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[3],
            1e-2,
            self._std_weight_position * mean[3]]
        std_vel = [
            self._std_weight_velocity * mean[3],
            self._std_weight_velocity * mean[3],
            1e-5,
            self._std_weight_velocity * mean[3]]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

        mean = np.dot(self._motion_mat, mean)
        covariance = np.linalg.multi_dot((
            self._motion_mat, covariance, self._motion_mat.T)) + motion_cov
        return mean, covariance

    def project(self, mean, covariance):
        """Project state distribution to measurement space."""
        std = [
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[3],
            1e-1,
            self._std_weight_position * mean[3]]
        innovation_cov = np.diag(np.square(std))

        mean = np.dot(self._update_mat, mean)
        covariance = np.linalg.multi_dot((
            self._update_mat, covariance, self._update_mat.T)) + innovation_cov
        return mean, covariance

    def update(self, mean, covariance, measurement):
        """Run Kalman filter correction step."""
        projected_mean, projected_cov = self.project(mean, covariance)

        chol_factor, lower = scipy.linalg.cho_factor(
            projected_cov, lower=True, check_finite=False)
        kalman_gain = scipy.linalg.cho_solve(
            (chol_factor, lower), np.dot(covariance, self._update_mat.T).T,
            check_finite=False).T
        innovation = measurement - projected_mean

        new_mean = mean + np.dot(innovation, kalman_gain.T)
        new_covariance = covariance - np.linalg.multi_dot((
            kalman_gain, projected_cov, kalman_gain.T))
        return new_mean, new_covariance


def bbox_to_xyah(bbox):
    """Convert [x, y, w, h] to [x_center, y_center, aspect_ratio, height]."""
    x, y, w, h = bbox
    cx = x + w / 2
    cy = y + h / 2
    a = w / float(h) if h > 0 else 0
    return np.array([cx, cy, a, h])


def xyah_to_bbox(xyah):
    """Convert [x_center, y_center, aspect_ratio, height] to [x, y, w, h]."""
    cx, cy, a, h = xyah
    w = a * h
    x = cx - w / 2
    y = cy - h / 2
    return np.array([x, y, w, h])


def compute_iou_matrix(bboxes1, bboxes2):
    """Compute IoU distance matrix."""
    if len(bboxes1) == 0 or len(bboxes2) == 0:
        return np.zeros((len(bboxes1), len(bboxes2)))

    matrix = np.zeros((len(bboxes1), len(bboxes2)))
    for i, box1 in enumerate(bboxes1):
        for j, box2 in enumerate(bboxes2):
            x1, y1, w1, h1 = box1
            x2, y2, w2, h2 = box2
            
            xi1 = max(x1, x2)
            yi1 = max(y1, y2)
            xi2 = min(x1 + w1, x2 + w2)
            yi2 = min(y1 + h1, y2 + h2)
            
            if xi2 <= xi1 or yi2 <= yi1:
                iou = 0.0
            else:
                intersection = (xi2 - xi1) * (yi2 - yi1)
                union = w1 * h1 + w2 * h2 - intersection
                iou = intersection / union if union > 0 else 0.0
            
            matrix[i, j] = 1 - iou # Return cost (distance)
    return matrix


class Track:
    """Represents a single tracked object."""
    def __init__(self, bbox, score, class_id, track_id):
        self.track_id = track_id
        self.class_id = class_id
        self.score = score
        self.state = "ACTIVE" # ACTIVE, LOST
        self.age = 0
        
        # Line Crossing tracking (2-line sequential)
        self.centroid_x_history = []
        self.centroid_y_history = []
        cx = bbox[0] + bbox[2] / 2
        cy = bbox[1] + bbox[3] / 2
        self.centroid_x_history.append(cx)
        self.centroid_y_history.append(cy)
        self.entry_counted = False
        self.exit_counted = False

        # 2-line crossing state flags
        self.crossed_a_down = False
        self.crossed_b_down = False
        self.crossed_b_up = False
        self.crossed_a_up = False
        self.last_zone = None

        # Kalman state
        self.mean, self.covariance = None, None
        
    def update(self, bbox, score, kf):
        """Update track with new detection."""
        self.score = score
        self.age = 0
        self.state = "ACTIVE"

        prev_cy = (self.centroid_y_history[-1] if self.centroid_y_history else None)

        cx = bbox[0] + bbox[2] / 2
        cy = bbox[1] + bbox[3] / 2
        self.centroid_x_history.append(cx)
        self.centroid_y_history.append(cy)

        if len(self.centroid_y_history) > 10:
            self.centroid_x_history.pop(0)
            self.centroid_y_history.pop(0)

        measurement = bbox_to_xyah(bbox)
        self.mean, self.covariance = kf.update(self.mean, self.covariance, measurement)

    def mark_lost(self):
        """Mark track as lost."""
        self.state = "LOST"
        self.age += 1

    def get_bbox(self):
        """Get current bounding box prediction."""
        if self.mean is None:
            return [0, 0, 0, 0]
        return xyah_to_bbox(self.mean[:4]).tolist()


class TwoLineCrossDetector:
    """
    2 fixed virtual lines — sequential zone crossing for CHECK_IN/CHECK_OUT.

    3 Zones (horizontal):
      Zone 1: above line_a     → outside fridge
      Zone 2: between A and B  → threshold
      Zone 3: below line_B     → inside fridge

    CHECK_IN  (enter):  Zone 1 → 2 → 3 (cross A then B downward)
    CHECK_OUT (leave):  Zone 3 → 2 → 1 (cross B then A upward)
    """
    def __init__(self, line_a_pos: int = 160, line_b_pos: int = 320, line_type: str = 'horizontal'):
        self.line_a_pos = line_a_pos
        self.line_b_pos = line_b_pos
        self.line_type = line_type
        self.qty_changes: Dict[int, int] = {}

    def set_virtual_lines(self, line_a: int, line_b: int, line_type: str = 'horizontal'):
        """Set fixed positions for both virtual lines."""
        self.line_a_pos = line_a
        self.line_b_pos = line_b
        self.line_type = line_type
        logger.info(f"2-line detector updated: A={line_a}, B={line_b} (type={line_type})")

    def _get_zone(self, coord: float) -> int:
        """Map a coordinate to zone 1|2|3."""
        if coord < self.line_a_pos:
            return 1
        if coord < self.line_b_pos:
            return 2
        return 3

    def check_crossing(self, track: Track):
        """
        Check 2-line sequential crossing for a track.
        Uses prev/current centroid to detect zone transitions.
        """
        if len(track.centroid_y_history) < 2 or len(track.centroid_x_history) < 2:
            return

        if self.line_type == 'horizontal':
            curr_coord = track.centroid_y_history[-1]
            prev_coord = track.centroid_y_history[-2]
        else:
            curr_coord = track.centroid_x_history[-1]
            prev_coord = track.centroid_x_history[-2]

        prev_zone = self._get_zone(prev_coord)
        curr_zone = self._get_zone(curr_coord)

        if prev_zone == curr_zone:
            return

        class_id = track.class_id
        food_name = _get_food_name(class_id)

        # --- Zone transitions ---
        if prev_zone == 1 and curr_zone == 2:
            # Crossed line A downward → start entry sequence
            track.crossed_a_down = True
            track.crossed_b_up = False
            track.crossed_a_up = False
            track.crossed_b_down = False
            logger.debug(f"Track {track.track_id}: crossed A down (zone 1→2)")

        elif prev_zone == 2 and curr_zone == 3:
            # Crossed line B downward
            track.crossed_b_down = True
            if track.crossed_a_down and not track.entry_counted:
                self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) + 1
                track.entry_counted = True
                track.exit_counted = False
                track.crossed_a_down = False
                track.crossed_b_down = False
                logger.info(f">>> notify: Track ID {track.track_id} CHECKED IN → '"+food_name+f"' (class={class_id}, +1) via 2-line")

        elif prev_zone == 3 and curr_zone == 2:
            # Crossed line B upward → start exit sequence
            track.crossed_b_up = True
            track.crossed_a_down = False
            track.crossed_b_down = False
            track.crossed_a_up = False
            logger.debug(f"Track {track.track_id}: crossed B up (zone 3→2)")

        elif prev_zone == 2 and curr_zone == 1:
            # Crossed line A upward
            track.crossed_a_up = True
            if track.crossed_b_up and not track.exit_counted:
                self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) - 1
                track.exit_counted = True
                track.entry_counted = False
                track.crossed_b_up = False
                track.crossed_a_up = False
                logger.info(f">>> notify: Track ID {track.track_id} CHECKED OUT → '"+food_name+f"' (class={class_id}, -1) via 2-line")

        # Direct zone 1→3 or 3→1: complete crossing in one frame — count directly
        elif prev_zone == 1 and curr_zone == 3 and not track.entry_counted:
            self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) + 1
            track.entry_counted = True
            track.exit_counted = False
            track.crossed_a_down = False
            track.crossed_b_down = False
            logger.info(f">>> notify: Track ID {track.track_id} CHECKED IN (fast) → '"+food_name+f"' (class={class_id}, +1) via 2-line")

        elif prev_zone == 3 and curr_zone == 1 and not track.exit_counted:
            self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) - 1
            track.exit_counted = True
            track.entry_counted = False
            track.crossed_b_up = False
            track.crossed_a_up = False
            logger.info(f">>> notify: Track ID {track.track_id} CHECKED OUT (fast) → '"+food_name+f"' (class={class_id}, -1) via 2-line")

    def get_and_clear_changes(self) -> Dict[int, int]:
        """Return the net changes and clear the buffer."""
        changes = self.qty_changes.copy()
        self.qty_changes.clear()
        return {k: v for k, v in changes.items() if v != 0}


class ByteTracker:
    """
    ByteTrack multi-object tracker implementation.
    Two-stage matching:
    1. High confidence detections matched via Kalman + IoU.
    2. Low confidence detections matched to remaining tracks via IoU to handle occlusion.
    """
    def __init__(self, max_age: int = 30, high_thresh: float = 0.85, match_thresh: float = 0.8):
        self.max_age = max_age
        self.high_thresh = high_thresh
        self.match_thresh = match_thresh
        
        self.kf = KalmanFilter()
        self.tracks: List[Track] = []
        self.next_track_id = 1
        
        self.line_detector = TwoLineCrossDetector(line_a_pos=160, line_b_pos=320)
        
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracker with new detections.
        """
        # Split detections into high and low score
        det_high = [d for d in detections if d['confidence'] >= self.high_thresh]
        det_low = [d for d in detections if d['confidence'] < self.high_thresh]
        
        # Predict states of all active and lost tracks
        for track in self.tracks:
            track.mean, track.covariance = self.kf.predict(track.mean, track.covariance)
            
        # --- Stage 1: Match high score detections ---
        unmatched_tracks, unmatched_det_high = self._match(self.tracks, det_high)
        
        # --- Stage 2: Match low score detections to unmatched tracks ---
        unmatched_tracks_stage1 = [self.tracks[i] for i in unmatched_tracks]
        unmatched_tracks_stage2, unmatched_det_low = self._match(unmatched_tracks_stage1, det_low)
        
        # Handle unmatched high score detections (new tracks)
        for i in unmatched_det_high:
            det = det_high[i]
            track = Track(det['bbox'], det['confidence'], det['class_id'], self.next_track_id)
            track.mean, track.covariance = self.kf.initiate(bbox_to_xyah(det['bbox']))
            self.tracks.append(track)
            self.next_track_id += 1
            logger.info(">>> notify start tracking: new Track ID {} for '{}' (class_id={}, conf={:.2f})".format(
                track.track_id, _get_food_name(det['class_id']), det['class_id'], det['confidence']))
            
        # Handle lost tracks
        active_tracks = []
        for track in self.tracks:
            if track not in unmatched_tracks_stage1 or track in [unmatched_tracks_stage1[i] for i in unmatched_tracks_stage2]:
                # Either matched in stage 1, or lost in stage 1 but NOT matched in stage 2 -> meaning it is lost
                pass # Logic handled in _match updates
                
            if track.state == "LOST" and track.age > self.max_age:
                continue # Remove track
                
            active_tracks.append(track)
            
            # Update Line Crossing logic
            self.line_detector.check_crossing(track)
            
        self.tracks = active_tracks
        
        # Format output
        results = []
        for track in self.tracks:
            if track.state == "ACTIVE":
                results.append({
                    'track_id': track.track_id,
                    'bbox': track.get_bbox(),
                    'confidence': track.score,
                    'class_id': track.class_id
                })
                
        return results
        
    def _match(self, tracks: List[Track], detections: List[Dict]) -> Tuple[List[int], List[int]]:
        """Match tracks and detections using IoU and Hungarian Algorithm."""
        if not tracks or not detections:
            return list(range(len(tracks))), list(range(len(detections)))
            
        track_bboxes = [t.get_bbox() for t in tracks]
        det_bboxes = [d['bbox'] for d in detections]
        
        cost_matrix = compute_iou_matrix(track_bboxes, det_bboxes)
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        unmatched_tracks = list(range(len(tracks)))
        unmatched_dets = list(range(len(detections)))
        
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] > self.match_thresh:
                continue
                
            track = tracks[r]
            det = detections[c]
            
            # Update track
            track.update(det['bbox'], det['confidence'], self.kf)
            
            unmatched_tracks.remove(r)
            unmatched_dets.remove(c)
            
        for r in unmatched_tracks:
            tracks[r].mark_lost()
            
        return unmatched_tracks, unmatched_dets

    def get_quantity_change(self) -> Dict[int, int]:
        """Fetch the exact net entry/exit changes."""
        return self.line_detector.get_and_clear_changes()

    def reset(self):
        """Reset tracker state."""
        self.tracks.clear()
        self.next_track_id = 1
        self.line_detector.qty_changes.clear()
