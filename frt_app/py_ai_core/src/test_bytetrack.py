import pytest
from ByteTracker import ByteTracker, Track

LINE_A = 160
LINE_B = 320


def make_tracker():
    tracker = ByteTracker()
    tracker.line_detector.set_virtual_lines(LINE_A, LINE_B)
    return tracker


def test_bytetrack_entry():
    """Object moves top→bottom crossing A then B → CHECK_IN."""
    tracker = make_tracker()

    # Smooth top-to-bottom motion with overlapping bboxes
    for y in range(50, 400, 30):
        cy = y - 40
        dets = [{'bbox': [100, y, 100, 100], 'confidence': 0.9, 'class_id': 5}]
        tracker.update(dets)

    changes = tracker.get_quantity_change()
    assert changes.get(5) == 1, f"Expected +1 for class 5, got {changes}"


def test_bytetrack_exit():
    """Object moves bottom→top crossing B then A → CHECK_OUT."""
    tracker = make_tracker()

    for y in range(400, 50, -30):
        cy = y - 40
        dets = [{'bbox': [100, y, 100, 100], 'confidence': 0.9, 'class_id': 2}]
        tracker.update(dets)

    changes = tracker.get_quantity_change()
    assert changes.get(2) == -1, f"Expected -1 for class 2, got {changes}"


def test_bytetrack_midframe_no_false():
    """Object appearing between lines does NOT trigger crossing."""
    tracker = make_tracker()

    for y in range(180, 300, 20):
        dets = [{'bbox': [100, y, 80, 80], 'confidence': 0.9, 'class_id': 3}]
        tracker.update(dets)

    changes = tracker.get_quantity_change()
    assert changes.get(3) is None, f"Expected no crossing, got {changes}"


def test_bytetrack_occlusion():
    """Track identity maintained through occlusion (low conf)."""
    tracker = make_tracker()

    dets = [{'bbox': [100, 100, 100, 100], 'confidence': 0.9, 'class_id': 1}]
    res = tracker.update(dets)
    track_id = res[0]['track_id']

    dets = [{'bbox': [105, 105, 100, 100], 'confidence': 0.3, 'class_id': 1}]
    res = tracker.update(dets)
    assert res[0]['track_id'] == track_id, "Track ID should persist through occlusion"


if __name__ == "__main__":
    test_bytetrack_entry()
    test_bytetrack_exit()
    test_bytetrack_midframe_no_false()
    test_bytetrack_occlusion()
    print("All tests passed successfully!")
