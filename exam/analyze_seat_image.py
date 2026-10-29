"""Analyze face-box positions against an exam seat plan in one still image."""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import DEFAULT_MODEL, DEFAULT_SCORE_THRESHOLD, YuNetFaceDetector
from exam.seat_plan import load_plan, map_face_boxes_to_seats


def analyze_image(plan, image, detector):
    """Return geometry-only seat occupancy observations for a BGR image."""
    height, width = image.shape[:2]
    expected = plan["camera"]
    if (width, height) != (expected["frame_width"], expected["frame_height"]):
        raise ValueError(
            f"Image is {width}x{height}, but the seat plan expects "
            f"{expected['frame_width']}x{expected['frame_height']}. "
            "Update the plan using the exact camera frame dimensions."
        )
    detections = detector.detect(image)
    boxes = [(left, top, right, bottom) for left, top, right, bottom, _ in detections]
    result = map_face_boxes_to_seats(plan, boxes)
    result["frame"] = {"width": width, "height": height}
    result["face_detection_count"] = len(detections)
    result["detector_score_threshold"] = detector.score_threshold
    return result, detections


def annotate(image, plan, result, detections):
    height, width = image.shape[:2]
    status_by_seat = {seat["seat_id"]: seat for seat in result["seats"]}
    for seat in plan["seats"]:
        observation = status_by_seat[seat["seat_id"]]
        count = observation["face_count"]
        ambiguous = observation["ambiguous_face_count"]
        color = (
            (180, 0, 180) if ambiguous else
            (0, 160, 0) if count == 1 else
            (0, 165, 255) if count == 0 else
            (0, 0, 220)
        )
        points = np.array(
            [[round(x * width), round(y * height)] for x, y in seat["zone"]],
            dtype=np.int32,
        )
        cv2.polylines(image, [points], True, color, 2)
        label = f"{seat['seat_id']}: ambiguous" if ambiguous else f"{seat['seat_id']}: {count} face(s)"
        x, y = points[0]
        cv2.putText(image, label, (int(x), max(20, int(y) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    for index, (left, top, right, bottom, score) in enumerate(detections, start=1):
        cv2.rectangle(image, (left, top), (right, bottom), (255, 180, 0), 2)
        cv2.putText(
            image,
            f"Face {index} ({score:.2f})",
            (left, max(20, top - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 180, 0),
            2,
        )
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="calibrated seat-plan JSON")
    parser.add_argument("--image", type=Path, required=True, help="still image from the configured camera")
    parser.add_argument("--model", type=Path, help="optional YuNet ONNX model path")
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument("--annotated-output", type=Path, help="optional local image output")
    parser.add_argument("--json-output", type=Path, help="optional geometry-only JSON report")
    parser.add_argument("--no-display", action="store_true", help="do not open an image window")
    args = parser.parse_args()
    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")

    try:
        plan = load_plan(args.plan)
        image = cv2.imread(str(args.image))
        if image is None:
            raise ValueError(f"Could not read image: {args.image}")
        detector = YuNetFaceDetector(
            args.model if args.model else DEFAULT_MODEL,
            args.score_threshold,
        )
        result, detections = analyze_image(plan, image, detector)
    except (OSError, ValueError, FileNotFoundError, RuntimeError, cv2.error) as exc:
        raise SystemExit(str(exc)) from exc

    for seat in result["seats"]:
        print(
            f"Seat {seat['seat_id']}: {seat['occupancy_observation']} "
            f"({seat['face_count']} assigned face(s), {seat['ambiguous_face_count']} ambiguous)"
        )
    print(f"Ambiguous face positions: {result['ambiguous_detection_count']}")
    print(f"Faces outside configured seat zones: {result['unassigned_detection_count']}")
    print("These face-position observations do not identify students or determine seating violations.")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Saved geometry-only report: {args.json_output}")

    if args.annotated_output:
        annotated = annotate(image.copy(), plan, result, detections)
        args.annotated_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.annotated_output), annotated):
            raise SystemExit(f"Could not write annotated image: {args.annotated_output}")
        print(f"Saved annotated image: {args.annotated_output}")

    if not args.no_display:
        cv2.imshow("Exam seat-zone observations", annotate(image, plan, result, detections))
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
