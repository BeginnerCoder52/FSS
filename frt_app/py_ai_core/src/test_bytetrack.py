import pytest
from ByteTracker import ByteTracker, Track

def test_bytetrack_entry():
    """Test object moving top to bottom, crossing line."""
    tracker = ByteTracker()
    
    # Simulate an object moving from y=100 down to y=300 (crossing y=240)
    # class_id = 5
    
    # Frame 1: Top (y_center=150)
    dets = [{'bbox': [100, 100, 100, 100], 'confidence': 0.9, 'class_id': 5}]
    tracker.update(dets)
    
    # Frame 2: Top (y_center=200)
    dets = [{'bbox': [100, 150, 100, 100], 'confidence': 0.9, 'class_id': 5}]
    tracker.update(dets)
    
    # Frame 3: Bottom (y_center=250) - crosses line!
    dets = [{'bbox': [100, 200, 100, 100], 'confidence': 0.9, 'class_id': 5}]
    tracker.update(dets)
    
    # Frame 4: Bottom (y_center=300)
    dets = [{'bbox': [100, 250, 100, 100], 'confidence': 0.9, 'class_id': 5}]
    tracker.update(dets)
    
    changes = tracker.get_quantity_change()
    assert changes.get(5) == 1, f"Expected +1 for class 5, got {changes}"

def test_bytetrack_exit():
    """Test object moving bottom to top, crossing line."""
    tracker = ByteTracker()
    
    # Frame 1: Bottom (y_center=350)
    dets = [{'bbox': [100, 300, 100, 100], 'confidence': 0.9, 'class_id': 2}]
    tracker.update(dets)
    
    # Frame 2: Bottom (y_center=300)
    dets = [{'bbox': [100, 250, 100, 100], 'confidence': 0.9, 'class_id': 2}]
    tracker.update(dets)
    
    # Frame 3: Top (y_center=250)
    dets = [{'bbox': [100, 200, 100, 100], 'confidence': 0.9, 'class_id': 2}]
    tracker.update(dets)
    
    # Frame 4: Top (y_center=200) - crosses line!
    dets = [{'bbox': [100, 150, 100, 100], 'confidence': 0.9, 'class_id': 2}]
    tracker.update(dets)
    
    changes = tracker.get_quantity_change()
    assert changes.get(2) == -1, f"Expected -1 for class 2, got {changes}"

def test_bytetrack_occlusion():
    """Test object identity maintained through occlusion."""
    tracker = ByteTracker()
    
    # Frame 1: High confidence
    dets = [{'bbox': [100, 100, 100, 100], 'confidence': 0.9, 'class_id': 1}]
    res = tracker.update(dets)
    track_id = res[0]['track_id']
    
    # Frame 2: Low confidence (Occlusion)
    dets = [{'bbox': [105, 105, 100, 100], 'confidence': 0.3, 'class_id': 1}]
    res = tracker.update(dets)
    assert res[0]['track_id'] == track_id, "Track ID should remain the same during occlusion"
    
if __name__ == "__main__":
    test_bytetrack_entry()
    test_bytetrack_exit()
    test_bytetrack_occlusion()
    print("All tests passed successfully!")
