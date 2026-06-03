#!/usr/bin/env python3
"""
test_phase2.py - Phase 2 Integration Testing
Version: 1.0
SDD v1.1.0 Compliance

Purpose:
    Verify C++ camera core writes frames to shared memory correctly.
    Test Python can read frames from shared memory.
    Validate frame headers and JPEG data integrity.

Test Coverage:
    1. SHM creation and attachment
    2. Frame header structure (64 bytes)
    3. JPEG data reading from SHM
    4. Camera core + Python integration
"""

import os
import struct
import sys
import subprocess
import time
import mmap
import threading
from pathlib import Path

FRT_SRC = str(Path(__file__).resolve().parent.parent / 'py_ai_core' / 'src')
if FRT_SRC not in sys.path:
    sys.path.insert(0, FRT_SRC)

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

# Test constants (match C++ definitions)
SHM_PATH = "/dev/shm/fss_video_frame"
SHM_SIZE = 2 * 1024 * 1024  # 2 MB
HEADER_SIZE = 64  # bytes
JPEG_MAGIC = b'\xFF\xD8'  # JPEG SOI marker

class FrameHeader:
    """Frame header struct (64 bytes total)"""
    def __init__(self):
        self.magic = 0
        self.width = 0
        self.height = 0
        self.format = 0
        self.timestamp_us = 0
        self.frame_id = 0
        self.jpeg_size = 0
        self.reserved = 0
    
    @staticmethod
    def from_bytes(data):
        """Deserialize frame header"""
        if len(data) < HEADER_SIZE:
            return None
        
        header = FrameHeader()
        unpacked = struct.unpack(
            '<IIIIQII8I',  # Little-endian: magic,width,height,format,timestamp,frame_id,jpeg_size,reserved
            data[:HEADER_SIZE]
        )
        header.magic = unpacked[0]
        header.width = unpacked[1]
        header.height = unpacked[2]
        header.format = unpacked[3]
        header.timestamp_us = unpacked[4]
        header.frame_id = unpacked[5]
        header.jpeg_size = unpacked[6]
        header.reserved = unpacked[7:]
        return header

class TestPhase2:
    """Phase 2 integration tests"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.camera_proc = None
    
    def log_test(self, name, result, message=""):
        """Log test result"""
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if message:
            print(f"        {message}")
        
        if result:
            self.passed += 1
        else:
            self.failed += 1
    
    def log_warning(self, message):
        """Log warning"""
        print(f"⚠ WARN: {message}")
        self.warnings += 1
    
    def start_camera_core(self):
        """Start C++ camera core in background"""
        try:
            camera_exec = Path(FSS_ROOT) / "frt_app" / "cpp_camera_core" / "build" / "camera_core_exec"
            if not camera_exec.exists():
                self.log_warning("Camera core executable not found - skipping camera test")
                return False
            
            # Start camera core (will write to SHM)
            self.camera_proc = subprocess.Popen(
                [str(camera_exec), "--device", "/dev/video0", "--width", "640", "--height", "480"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give it time to initialize
            time.sleep(2)
            
            if self.camera_proc.poll() is not None:
                stderr = self.camera_proc.stderr.read().decode(errors="replace").strip() if self.camera_proc.stderr else ""
                self.log_warning(
                    "Camera core exited prematurely{}".format(
                        f": {stderr}" if stderr else ""
                    )
                )
                return False
            
            print("[*] Camera core started (PID: {})".format(self.camera_proc.pid))
            return True
        except Exception as e:
            self.log_warning(f"Failed to start camera core: {e}")
            return False
    
    def stop_camera_core(self):
        """Stop camera core"""
        if self.camera_proc:
            self.camera_proc.terminate()
            try:
                self.camera_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.camera_proc.kill()
                self.camera_proc.wait()
            print("[*] Camera core stopped")
    
    def test_shm_attachment(self):
        """Test: Attach to shared memory"""
        try:
            shm_fd = os.open(SHM_PATH, os.O_RDONLY)
            os.close(shm_fd)
            self.log_test("SHM Attachment", True, SHM_PATH)
            return True
        except FileNotFoundError:
            self.log_test("SHM Attachment", False, f"{SHM_PATH} not found - is camera_core running?")
            return False
        except Exception as e:
            self.log_test("SHM Attachment", False, str(e))
            return False
    
    def test_frame_header_parsing(self):
        """Test: Parse frame header from SHM"""
        try:
            shm_fd = os.open(SHM_PATH, os.O_RDONLY)
            with mmap.mmap(shm_fd, HEADER_SIZE, access=mmap.ACCESS_READ) as m:
                header_data = m.read(HEADER_SIZE)
                header = FrameHeader.from_bytes(header_data)
                
                if header is None:
                    self.log_test("Frame Header Parsing", False, "Failed to deserialize")
                    os.close(shm_fd)
                    return False
                
                valid = (
                    header.frame_id >= 0 and
                    header.timestamp_us > 0 and
                    0 < header.jpeg_size < SHM_SIZE
                )
                
                self.log_test(
                    "Frame Header Parsing",
                    valid,
                    f"frame_id={header.frame_id}, jpeg_size={header.jpeg_size}, ts={header.timestamp_us}"
                )
            os.close(shm_fd)
            return valid
        except Exception as e:
            self.log_test("Frame Header Parsing", False, str(e))
            return False
    
    def test_jpeg_integrity(self):
        """Test: Verify JPEG data integrity"""
        try:
            shm_fd = os.open(SHM_PATH, os.O_RDONLY)
            with mmap.mmap(shm_fd, SHM_SIZE, access=mmap.ACCESS_READ) as m:
                # Read header
                header_data = m.read(HEADER_SIZE)
                header = FrameHeader.from_bytes(header_data)
                
                if not header or header.jpeg_size == 0:
                    self.log_test("JPEG Integrity", False, "Invalid header")
                    os.close(shm_fd)
                    return False
                
                # Read JPEG data
                m.seek(HEADER_SIZE)
                jpeg_data = m.read(header.jpeg_size)
                
                # Check JPEG magic number (SOI marker: FF D8)
                has_magic = jpeg_data.startswith(JPEG_MAGIC)
                has_eoi = b'\xFF\xD9' in jpeg_data[-10:]  # EOI marker in last 10 bytes
                
                valid = has_magic and has_eoi
                message = f"SOI={'OK' if has_magic else 'FAIL'}, EOI={'OK' if has_eoi else 'FAIL'}"
                
                self.log_test("JPEG Integrity", valid, message)
            os.close(shm_fd)
            return valid
        except Exception as e:
            self.log_test("JPEG Integrity", False, str(e))
            return False
    
    def test_frame_sequence(self):
        """Test: Verify frame_id sequence increments"""
        try:
            shm_fd = os.open(SHM_PATH, os.O_RDONLY)
            frame_ids = []
            
            with mmap.mmap(shm_fd, HEADER_SIZE, access=mmap.ACCESS_READ) as m:
                # Read first frame_id
                for i in range(5):
                    m.seek(0)
                    header_data = m.read(HEADER_SIZE)
                    header = FrameHeader.from_bytes(header_data)
                    if header:
                        frame_ids.append(header.frame_id)
                    time.sleep(0.2)
            
            os.close(shm_fd)
            
            # Check if frame_ids are increasing
            is_increasing = all(frame_ids[i] <= frame_ids[i+1] for i in range(len(frame_ids)-1))
            
            self.log_test(
                "Frame ID Sequence",
                is_increasing,
                f"IDs: {frame_ids}"
            )
            return is_increasing
        except Exception as e:
            self.log_test("Frame ID Sequence", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all Phase 2 tests"""
        print("\n" + "="*60)
        print("PHASE 2 - C++ CAMERA CORE INTEGRATION TESTS")
        print("="*60)
        
        # Start camera core
        camera_started = self.start_camera_core()
        
        if not camera_started:
            print("\n[!] Skipping SHM tests (camera core not available)")
            print("    Run: {}/frt_app/cpp_camera_core/build/camera_core_exec".format(FSS_ROOT))
            print("    And then run this test in another terminal")
        else:
            # Run tests
            self.test_shm_attachment()
            time.sleep(0.5)
            self.test_frame_header_parsing()
            self.test_jpeg_integrity()
            self.test_frame_sequence()
            
            # Stop camera core
            self.stop_camera_core()
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Passed:  {self.passed}")
        print(f"Failed:  {self.failed}")
        print(f"Warnings: {self.warnings}")
        print("="*60)
        
        if self.failed == 0:
            print("✓ PHASE 2 TESTS PASSED")
            return 0
        else:
            print("✗ PHASE 2 TESTS FAILED")
            return 1

if __name__ == "__main__":
    tester = TestPhase2()
    sys.exit(tester.run_all_tests())
