"""Compare detector coverage on the local enrollment photos (not accuracy)."""

import argparse
from collections import Counter
from pathlib import Path

import cv2
import face_recognition

from face_detection import DEFAULT_MODEL, YuNetFaceDetector


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_DIR / "dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def bucket(count):
    if count == 0:
        return "zero"
    if count == 1:
        return "one"
    return "multiple"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--score-threshold", type=float, default=0.85)
    args = parser.parse_args()
    if not args.dataset.is_dir():
        parser.error(f"dataset directory does not exist: {args.dataset}")

    images = sorted(
        path for path in args.dataset.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        parser.error(f"no supported images found under {args.dataset}")

    yunet = YuNetFaceDetector(score_threshold=args.score_threshold)
    haar = None
    if hasattr(cv2, "CascadeClassifier"):
        candidate = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if not candidate.empty():
            haar = candidate

    counts = {
        "YuNet": Counter(),
        "HOG": Counter(),
    }
    if haar is not None:
        counts["Haar"] = Counter()
    unreadable = 0
    for path in images:
        bgr = cv2.imread(str(path))
        if bgr is None:
            unreadable += 1
            continue

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        counts["YuNet"][bucket(len(yunet.detect(bgr)))] += 1
        if haar is not None:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            counts["Haar"][bucket(len(haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)))] += 1
        counts["HOG"][bucket(len(face_recognition.face_locations(rgb, model="hog")))] += 1

    print(f"Images scanned: {len(images)} (unreadable: {unreadable})")
    print("Counts are images with zero, exactly one, or multiple detected faces:")
    for detector_name in ("YuNet", "Haar", "HOG"):
        if detector_name not in counts:
            print(f"{detector_name:5}  unavailable in this OpenCV build")
            continue
        result = counts[detector_name]
        print(
            f"{detector_name:5}  zero={result['zero']:3}  "
            f"one={result['one']:3}  multiple={result['multiple']:3}"
        )
    print("These are coverage counts on this enrollment set, not precision, recall, or accuracy.")
    print("The images were captured using a face detector, so they are not an independent test set.")


if __name__ == "__main__":
    main()
