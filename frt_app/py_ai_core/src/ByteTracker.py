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
        
        # Line Crossing tracking
        # We store centroid history (x and y)
        self.centroid_x_history = []
        self.centroid_y_history = []
        cx = bbox[0] + bbox[2] / 2
        cy = bbox[1] + bbox[3] / 2
        self.centroid_x_history.append(cx)
        self.centroid_y_history.append(cy)
        self.entry_counted = False
        self.exit_counted = False
        
        # Kalman state
        self.mean, self.covariance = None, None
        
    def update(self, bbox, score, kf):
        """Update track with new detection."""
        self.score = score
        self.age = 0
        self.state = "ACTIVE"
        
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


class LineCrossDetector:
    """Detects when objects cross a virtual boundary line."""
    def __init__(self, boundary_y: int = 240):
        # Default to horizontal line
        self.boundary_line = {
            'type': 'horizontal',
            'pos': boundary_y
        }
        self.qty_changes = {} # class_id -> change quantity (+ or -)
        
    def set_virtual_line(self, line_info: dict):
        """Set a dynamic virtual line detected from frame."""
        if line_info:
            self.boundary_line = line_info
            logger.info(f"LineCrossDetector updated with {line_info['type']} virtual line at {int(line_info['pos'])}")

    def check_crossing(self, track: Track):
        """
        Check if a track has crossed the boundary.
        Top -> Bottom (Outside -> Inside) = Entry (+1)
        Bottom -> Top (Inside -> Outside) = Exit (-1)
        Left -> Right (Outside -> Inside) = Entry (+1)
        Right -> Left (Inside -> Outside) = Exit (-1)
        """
        if len(track.centroid_y_history) < 2 or len(track.centroid_x_history) < 2:
            return
            
        line_type = self.boundary_line['type']
        pos = self.boundary_line['pos']
        
        if line_type == 'horizontal':
            start_pos = track.centroid_y_history[0]
            end_pos = track.centroid_y_history[-1]
        else: # vertical
            start_pos = track.centroid_x_history[0]
            end_pos = track.centroid_x_history[-1]
            
        # Outside to Inside (Entry)
        if start_pos < pos and end_pos >= pos and not track.entry_counted:
            class_id = track.class_id
            self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) + 1
            track.entry_counted = True
            track.exit_counted = False # Reset if it changes direction
            logger.info(f"Entry detected! Track ID {track.track_id}, Class {class_id} (+1) via {line_type} line")
            
        # Inside to Outside (Exit)
        elif start_pos > pos and end_pos <= pos and not track.exit_counted:
            class_id = track.class_id
            self.qty_changes[class_id] = self.qty_changes.get(class_id, 0) - 1
            track.exit_counted = True
            track.entry_counted = False # Reset if it changes direction
            logger.info(f"Exit detected! Track ID {track.track_id}, Class {class_id} (-1) via {line_type} line")

    def get_and_clear_changes(self) -> Dict[int, int]:
        """Return the net changes and clear the buffer."""
        changes = self.qty_changes.copy()
        self.qty_changes.clear()
        # Filter out 0 changes
        return {k: v for k, v in changes.items() if v != 0}


class ByteTracker:
    """
    ByteTrack multi-object tracker implementation.
    Two-stage matching:
    1. High confidence detections matched via Kalman + IoU.
    2. Low confidence detections matched to remaining tracks via IoU to handle occlusion.
    """
    def __init__(self, max_age: int = 30, high_thresh: float = 0.5, match_thresh: float = 0.8):
        self.max_age = max_age
        self.high_thresh = high_thresh
        self.match_thresh = match_thresh
        
        self.kf = KalmanFilter()
        self.tracks: List[Track] = []
        self.next_track_id = 1
        
        self.line_detector = LineCrossDetector(boundary_y=240)
        
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
