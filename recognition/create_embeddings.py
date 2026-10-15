"""Build YuNet-aligned face encodings from dataset/<student_id>/* images."""

import csv
import sys
from datetime import datetime
from pathlib import Path

import cv2
import face_recognition
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import DEFAULT_SCORE_THRESHOLD, YuNetFaceDetector


DATASET_DIR = PROJECT_DIR / "dataset"
OUTPUT_FILE = Path(__file__).resolve().parent / "face_embeddings.npz"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    args = parser.parse_args()
    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")

    encodings = []
    student_ids = []
    rejected = []

    if not DATASET_DIR.is_dir():
        raise SystemExit(f"Dataset directory not found: {DATASET_DIR}")

    try:
        detector = YuNetFaceDetector(score_threshold=args.score_threshold)
    except (FileNotFoundError, RuntimeError, cv2.error) as exc:
        raise SystemExit(f"Could not initialize YuNet: {exc}") from exc

    for student_dir in sorted(path for path in DATASET_DIR.iterdir() if path.is_dir()):
        for image_path in sorted(student_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            print(f"Processing {image_path.relative_to(PROJECT_DIR)}")
            try:
                bgr = cv2.imread(str(image_path))
                if bgr is None:
                    print("  Image unreadable; skipped")
                    rejected.append((str(image_path), "unreadable", 0))
                    continue
                detections = detector.detect(bgr)
                if len(detections) != 1:
                    result = "no_face" if not detections else "multiple_faces"
                    print(f"  {result.replace('_', ' ').title()} ({len(detections)} detected); skipped")
                    rejected.append((str(image_path), result, len(detections)))
                    continue

                left, top, right, bottom, _score = detections[0]
                location = (top, right, bottom, left)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                image_encodings = face_recognition.face_encodings(rgb, [location])
                if not image_encodings:
                    print("  Could not encode detected face; skipped")
                    rejected.append((str(image_path), "encoding_failed", 1))
                    continue
                encoding = image_encodings[0]
                encodings.append(encoding)
                student_ids.append(student_dir.name)
            except Exception as exc:
                print(f"  Could not process image: {exc}")
                rejected.append((str(image_path), f"error: {exc}", 0))

    if not encodings:
        raise SystemExit("No face encodings created. Check that dataset/<student_id>/ contains usable face images.")

    np.savez_compressed(
        OUTPUT_FILE,
        encodings=np.asarray(encodings, dtype=np.float64),
        names=np.asarray(student_ids),
    )
    print(f"Saved {len(encodings)} encodings for {len(set(student_ids))} students to {OUTPUT_FILE}")

    rejected_file = PROJECT_DIR / "reports" / "embedding_rejections" / f"rejected_{datetime.now():%Y%m%d_%H%M%S}.csv"
    rejected_file.parent.mkdir(parents=True, exist_ok=True)
    with rejected_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["image_path", "reason", "face_count"])
        writer.writerows(rejected)
    print(f"Rejected images ({len(rejected)}): {rejected_file}")


if __name__ == "__main__":
    main()
