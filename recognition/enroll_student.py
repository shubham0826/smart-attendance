"""Capture face samples into dataset/<student_id> with YuNet quality checks."""

import argparse
import re
import sys
from pathlib import Path

import cv2


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import DEFAULT_SCORE_THRESHOLD, YuNetFaceDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id", help="student ID used as the enrollment folder name")
    parser.add_argument("--count", type=int, default=20, help="number of accepted images to capture")
    parser.add_argument("--camera", type=int, default=0, help="camera device index")
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.student_id):
        parser.error("student_id may contain only letters, numbers, underscores, and hyphens")
    if args.count < 1:
        parser.error("--count must be at least 1")
    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")

    output_dir = PROJECT_DIR / "dataset" / args.student_id
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        int(match.group(1))
        for path in output_dir.glob("face_*.jpg")
        if (match := re.fullmatch(r"face_(\d+)\.jpg", path.name))
    ]
    next_index = max(existing, default=0) + 1

    try:
        detector = YuNetFaceDetector(score_threshold=args.score_threshold)
    except (FileNotFoundError, RuntimeError, cv2.error) as exc:
        raise SystemExit(f"Could not initialize YuNet: {exc}") from exc

    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}. Check the connection or camera index.")

    saved = 0
    print(f"Enrolling {args.student_id}: target {args.count} images")
    print("Center the student's face, vary angle and expression slightly, then press SPACE to save.")
    print("Only one clearly visible face can be saved. Press Q to finish early.")
    try:
        while saved < args.count:
            success, frame = camera.read()
            if not success:
                print("Could not read a camera frame.")
                break

            capture_frame = frame.copy()
            detections = detector.detect(frame)
            for left, top, right, bottom, score in detections:
                color = (0, 200, 0) if len(detections) == 1 and min(right - left, bottom - top) >= 80 else (0, 0, 220)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, f"Face {score:.2f}", (left, max(20, top - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if len(detections) == 1:
                left, top, right, bottom, _score = detections[0]
                face_size_ok = min(right - left, bottom - top) >= 80
            else:
                face_size_ok = False
            status = f"{args.student_id} | saved {saved}/{args.count} | "
            status += "SPACE: save" if face_size_ok else "show one larger face"
            cv2.putText(frame, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            cv2.imshow("Student Enrollment", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                if not face_size_ok:
                    print("Sample rejected: show exactly one face at least 80 pixels across.")
                    continue
                path = output_dir / f"face_{next_index}.jpg"
                if cv2.imwrite(str(path), capture_frame):
                    saved += 1
                    next_index += 1
                    print(f"Saved {saved}/{args.count}: {path}")
                else:
                    print(f"Could not save image: {path}")
    finally:
        camera.release()
        cv2.destroyAllWindows()

    print(f"Enrollment finished: saved {saved} image(s) in {output_dir}")
    return 0 if saved == args.count else 1


if __name__ == "__main__":
    raise SystemExit(main())
