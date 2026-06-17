"""
VirtualLineDetector.py - Fixed 2 Virtual Lines Configuration for Check-In/Check-Out
Version: 2.0

Purpose:
    Replaces the Hough Transform-based auto-detection with 2 fixed virtual lines.
    Line A (outer/top): Fridge mouth boundary — entering starts here.
    Line B (inner/bottom): Inside fridge — entry confirmed when both crossed.
    
    3 Zones:
      Zone 1: above Line A     → outside fridge
      Zone 2: between A and B  → threshold area
      Zone 3: below Line B     → inside fridge
    
    CHECK_IN  (enter): Zone 1 → 2 → 3 (cross A then B downward)
    CHECK_OUT (leave): Zone 3 → 2 → 1 (cross B then A upward)
"""

from loguru import logger
from typing import Dict
from dataclasses import dataclass


@dataclass
class FixedLineConfig:
    line_a_ratio: float = 0.33
    line_b_ratio: float = 0.66
    line_type: str = 'horizontal'

    def get_lines(self, frame_height: int) -> Dict:
        """Return 2 fixed virtual lines based on frame height."""
        line_a = int(frame_height * self.line_a_ratio)
        line_b = int(frame_height * self.line_b_ratio)

        if self.line_type == 'horizontal' and line_b <= line_a:
            line_b = line_a + 1
            logger.warning(f"Line B adjusted to {line_b} to ensure A < B")

        config = {
            'type': self.line_type,
            'line_a_pos': line_a,
            'line_b_pos': line_b,
        }
        logger.info(f"Fixed virtual lines set: A={line_a}, B={line_b} (type={self.line_type}, frame_h={frame_height})")
        return config


if __name__ == "__main__":
    cfg = FixedLineConfig()
    result = cfg.get_lines(480)
    print("Fixed lines:", result)
