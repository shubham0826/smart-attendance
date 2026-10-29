"""Run YuNet and face embeddings on a still image, then prepare review suggestions."""

import argparse
import json
import sys
from pathlib import Path

import cv2
import face_recognition
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import DEFAULT_MODEL, DEFAULT_SCORE_THRESHOLD, YuNetFaceDetector
from exam.compare_observations import compare_observations, validate_observations
from exam.seat_plan import load_plan
from recognition.matching import MATCH_THRESHOLD, find_best_candidate


def analyze_exam_frame(plan, image, detector, known_encodings, known_ids, match_threshold):
    height, width = image.shape[:2]
    if (width, height) != (
        plan["camera"]["frame_width"], plan["camera"]["frame_height"]
    ):
        raise ValueError(
            f"Image is {width}x{height}; seat plan expects "
            f"{plan['camera']['frame_width']}x{plan['camera']['frame_height']}."
        )

    detections = detector.detect(image)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    observations = []
    for left, top, right, bottom, detector_score in detections:
        face_location = (top, right, bottom, left)
        encodings = face_recognition.face_encodings(rgb_image, [face_location])
        if not encodings:
            identity_status = "uncertain"
            candidate_id = None
            match_distance = None
        else:
            best_id, match_distance, candidate = find_best_candidate(
                known_encodings, known_ids, encodings[0], match_threshold
            )
            identity_status = "candidate" if candidate else "unknown"
            candidate_id = best_id if candidate else None
        observations.append({
            "bbox": [left, top, right, bottom],
            "identity_status": identity_status,
            "candidate_student_id": candidate_id,
            "match_distance": match_distance,
            "detector_score": detector_score,
        })

    payload = {
        "exam_id": plan["exam_id"],
        "frame": {"width": width, "height": height},
        "observations": observations,
    }
    validated = validate_observations(payload, plan)
    review = compare_observations(plan, validated)
    return payload, review, detections


def annotate(image, plan, review, detections):
    height, width = image.shape[:2]
    status_by_seat = {seat["seat_id"]: seat["status"] for seat in review["seats"]}
    colors = {
        "candidate_match_for_review": (0, 170, 220),
        "possible_assignment_mismatch_for_review": (0, 0, 220),
        "uncertain": (0, 165, 255),
    }
    for seat in plan["seats"]:
        status = status_by_seat[seat["seat_id"]]
        color = colors[status]
        polygon = np.array(
            [[round(x * width), round(y * height)] for x, y in seat["zone"]],
            dtype=np.int32,
        )
        cv2.polylines(image, [polygon], True, color, 2)
        label = f"{seat['seat_id']}: {status.replace('_', ' ')}"
        x, y = polygon[0]
        cv2.putText(image, label, (int(x), max(20, int(y) - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.47, color, 2)

    for index, (left, top, right, bottom, score) in enumerate(detections, start=1):
        cv2.rectangle(image, (left, top), (right, bottom), (255, 180, 0), 2)
        cv2.putText(
            image,
            f"Face {index}: {score:.2f}",
            (left, max(20, top - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 180, 0),
            2,
        )
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="local calibrated seat plan")
    parser.add_argument("--image", type=Path, required=True, help="still image from the configured camera")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=PROJECT_DIR / "recognition" / "face_embeddings.npz",
        help="local face-embedding file (never uploaded by this command)",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="YuNet ONNX model path")
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=MATCH_THRESHOLD,
        help="experimental face-distance threshold; outputs remain review-only",
    )
    parser.add_argument("--json-output", type=Path, help="optional detailed local review report")
    parser.add_argument("--annotated-output", type=Path, help="optional annotated image output")
    parser.add_argument("--display", action="store_true", help="show an annotated image window")
    args = parser.parse_args()
    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")
    if not 0.0 <= args.match_threshold <= 1.0:
        parser.error("--match-threshold must be between 0 and 1")
    for output in (args.json_output, args.annotated_output):
        if output and output.exists():
            parser.error(f"output already exists; choose another path to avoid overwriting it: {output}")

    try:
        plan = load_plan(args.plan)
        image = cv2.imread(str(args.image))
        if image is None:
            raise ValueError(f"Could not read image: {args.image}")
        data = np.load(args.embeddings, allow_pickle=False)
        try:
            known_encodings = data["encodings"]
            known_ids = data["names"].astype(str)
            if len(known_encodings) == 0 or len(known_encodings) != len(known_ids):
                raise ValueError("Embedding file is empty or inconsistent. Rebuild the embeddings.")
            detector = YuNetFaceDetector(args.model, args.score_threshold)
            observations, review, detections = analyze_exam_frame(
                plan,
                image,
                detector,
                known_encodings,
                known_ids,
                args.match_threshold,
            )
        finally:
            data.close()
    except (OSError, ValueError, FileNotFoundError, RuntimeError, cv2.error) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Exam: {review['exam_id']} | face detections: {review['face_observation_count']}")
    for status, count in sorted(review["status_counts"].items()):
        print(f"  {status}: {count}")
    print(
        f"Ambiguous positions: {review['ambiguous_face_count']} | "
        f"outside seat zones: {review['outside_seat_zone_count']}"
    )
    print(f"Experimental match threshold: {args.match_threshold:.2f} (not independently validated).")
    print("Candidate matches, possible mismatches, and uncertain results all require teacher review.")

    result = {
        "model_settings": {
            "face_detector": "OpenCV YuNet",
            "detection_score_threshold": args.score_threshold,
            "face_match_threshold": args.match_threshold,
            "face_match_threshold_validated": False,
        },
        "observations": observations,
        "review": review,
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("x", encoding="utf-8") as file:
            json.dump(result, file, indent=2)
            file.write("\n")
        print(f"Saved detailed local review: {args.json_output}")

    annotated = None
    if args.annotated_output or args.display:
        annotated = annotate(image.copy(), plan, review, detections)
    if args.annotated_output:
        args.annotated_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.annotated_output), annotated):
            raise SystemExit(f"Could not write annotated image: {args.annotated_output}")
        print(f"Saved annotated image: {args.annotated_output}")
    if args.display:
        cv2.imshow("Exam seat review suggestions", annotated)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
