"""Verify Python, OpenCV, NumPy, and basic image writing for Phase 1."""

from pathlib import Path

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_DIR / "phase1_test.png"


print("Smart Attendance System")
print("Python AI environment is ready!")
print("OpenCV version:", cv2.__version__)
print("NumPy version:", np.__version__)

image = np.zeros((300, 500, 3), dtype=np.uint8)
cv2.putText(
    image,
    "Phase 1 Complete!",
    (40, 160),
    cv2.FONT_HERSHEY_SIMPLEX,
    1,
    (255, 255, 255),
    2,
)

if not cv2.imwrite(str(OUTPUT_FILE), image):
    raise SystemExit(f"Could not write test image: {OUTPUT_FILE}")

print("Test image saved successfully:", OUTPUT_FILE)
