"""Summarize YuNet detections across the captured enrollment image set.

This is a dataset sanity check, not a validated accuracy measurement because
the images do not have independent face-box annotations.
"""

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from face_detection import DEFAULT_MODEL, YuNetFaceDetector


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_DIR / "dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--score-threshold", type=float, default=0.85)
    parser.add_argument(
        "--review-dir", type=Path,
        default=PROJECT_DIR / "reports" / "face_detection_review",
        help="where to save a CSV and contact sheet for images without exactly one face",
    )
    args = parser.parse_args()

    if not args.dataset.is_dir():
        parser.error(f"dataset directory does not exist: {args.dataset}")
    paths = sorted(
        path for path in args.dataset.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not paths:
        parser.error(f"no supported images found under {args.dataset}")

    detector = YuNetFaceDetector(args.model, args.score_threshold)
    counts = {"no_face": 0, "one_face": 0, "multiple_faces": 0, "unreadable": 0}
    review_rows = []
    review_tiles = []
    for image_path in paths:
        image = cv2.imread(str(image_path))
        if image is None:
            counts["unreadable"] += 1
            review_rows.append((str(image_path), "unreadable", 0))
            continue
        detections = detector.detect(image)
        number_detected = len(detections)
        if number_detected == 0:
            counts["no_face"] += 1
        elif number_detected == 1:
            counts["one_face"] += 1
        else:
            counts["multiple_faces"] += 1
        if number_detected != 1:
            review_rows.append((str(image_path), "no_face" if number_detected == 0 else "multiple_faces", number_detected))
            preview = image.copy()
            for left, top, right, bottom, score in detections:
                cv2.rectangle(preview, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.putText(preview, f"{score:.2f}", (left, max(18, top - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            thumb_w, thumb_h = 240, 180
            thumb = cv2.resize(preview, (thumb_w, thumb_h))
            label = f"{image_path.parent.name}/{image_path.name}: {number_detected} face(s)"
            tile = np.full((thumb_h + 34, thumb_w, 3), 255, dtype=np.uint8)
            tile[:thumb_h] = thumb
            cv2.putText(tile, label[:36], (4, thumb_h + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
            review_tiles.append(tile)

    args.review_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.review_dir / "review.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["image_path", "result", "face_count"])
        writer.writerows(review_rows)

    contact_sheet_path = args.review_dir / "contact_sheet.jpg"
    if review_tiles:
        columns = 3
        rows = (len(review_tiles) + columns - 1) // columns
        tile_h, tile_w = review_tiles[0].shape[:2]
        sheet = np.full((rows * tile_h, columns * tile_w, 3), 245, dtype=np.uint8)
        for index, tile in enumerate(review_tiles):
            y, x = divmod(index, columns)
            sheet[y * tile_h:(y + 1) * tile_h, x * tile_w:(x + 1) * tile_w] = tile
        if not cv2.imwrite(str(contact_sheet_path), sheet):
            raise SystemExit(f"Could not save contact sheet: {contact_sheet_path}")

    print(f"Images scanned: {len(paths)}")
    print(f"Exactly one face detected: {counts['one_face']}")
    print(f"No faces detected: {counts['no_face']}")
    print(f"Multiple faces detected: {counts['multiple_faces']}")
    print(f"Unreadable images: {counts['unreadable']}")
    print(f"Review list: {csv_path}")
    if review_tiles:
        print(f"Review contact sheet: {contact_sheet_path}")
    else:
        print("No images need review.")
    print("This measures detections on the current enrollment set, not recognition accuracy.")


if __name__ == "__main__":
    main()
