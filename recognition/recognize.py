"""Recognize registered students from a webcam and record daily attendance."""

import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import face_recognition
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import DEFAULT_SCORE_THRESHOLD, YuNetFaceDetector
from database import attendance_store
from recognition.matching import find_best_candidate


EMBEDDINGS_FILE = Path(__file__).resolve().parent / "face_embeddings.npz"
CAMERA_INDEX = 0
FRAME_SCALE = 0.25


def load_attendance_for_today(today):
    """Return IDs already recorded today from the configured backend."""
    day = datetime.strptime(today, "%Y-%m-%d").date()
    return {
        row["student_id"] for row in attendance_store.list_attendance(day, day)
    }


def record_attendance(student_id, today, attended, detector_score=None, match_distance=None):
    """Record one attendance row per student per date."""
    if student_id in attended:
        return False
    now = datetime.now()
    inserted = attendance_store.record_check_in(
        student_id,
        datetime.strptime(today, "%Y-%m-%d").date(),
        now.time().replace(microsecond=0),
        detector_score=detector_score,
        match_distance=match_distance,
    )
    if not inserted:
        attended.add(student_id)
        return False
    attended.add(student_id)
    print(f"Attendance marked: {student_id} at {now.strftime('%H:%M:%S')}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detector", choices=("yunet", "hog"), default="yunet",
        help="face detector to use (default: YuNet; HOG is the legacy fallback)",
    )
    parser.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD)
    parser.add_argument(
        "--checkpoint-minutes",
        type=int,
        default=20,
        help="minutes between review-only presence checkpoints (default: 20)",
    )
    args = parser.parse_args()
    if not 0.0 <= args.score_threshold <= 1.0:
        parser.error("--score-threshold must be between 0 and 1")
    if args.checkpoint_minutes < 1:
        parser.error("--checkpoint-minutes must be at least 1")

    if not EMBEDDINGS_FILE.is_file() or EMBEDDINGS_FILE.stat().st_size == 0:
        raise SystemExit(
            f"Face embeddings not found at {EMBEDDINGS_FILE}. "
            "Run: python recognition/create_embeddings.py"
        )

    data = np.load(EMBEDDINGS_FILE, allow_pickle=False)
    known_encodings = data["encodings"]
    known_ids = data["names"].astype(str)
    if len(known_encodings) == 0 or len(known_encodings) != len(known_ids):
        raise SystemExit("Embedding file is empty or inconsistent. Rebuild the embeddings.")

    detector = None
    if args.detector == "yunet":
        try:
            detector = YuNetFaceDetector(score_threshold=args.score_threshold)
        except (FileNotFoundError, RuntimeError, cv2.error) as exc:
            data.close()
            raise SystemExit(f"Could not initialize YuNet: {exc}") from exc

    today = datetime.now().date().isoformat()
    attended = load_attendance_for_today(today)
    camera = cv2.VideoCapture(CAMERA_INDEX)
    if not camera.isOpened():
        raise SystemExit("Could not open the webcam. Check the camera connection and CAMERA_INDEX.")

    backend = attendance_store.backend()
    print(f"Recognizing students with {args.detector.upper()} using {backend.upper()} storage.")
    if args.detector == "yunet":
        print(f"YuNet score threshold: {args.score_threshold:.2f}")
    else:
        print("Using legacy HOG detection on quarter-size frames.")
    print("Press q in the camera window to stop.")
    session_id = None
    checkpoint_roster = []
    observed_since_checkpoint = set()
    checkpoint_interval = args.checkpoint_minutes * 60
    next_checkpoint = time.monotonic() + checkpoint_interval
    checkpoint_window_start = datetime.now().replace(microsecond=0)
    try:
        if backend == "mysql":
            checkpoint_roster = attendance_store.list_students()
            session_label = f"Recognition run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            session_id = attendance_store.start_class_session(session_label, args.checkpoint_minutes)
            print(
                f"Class session {session_id} started. Review-only checkpoints every "
                f"{args.checkpoint_minutes} minutes."
            )
        else:
            print("Periodic checkpoints are available with ATTENDANCE_STORAGE=mysql.")

        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read a frame from the webcam.")
                break

            if args.detector == "yunet":
                detections = detector.detect(frame)
                locations = [(top, right, bottom, left) for left, top, right, bottom, _ in detections]
                detector_scores = [score for _, _, _, _, score in detections]
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                encodings = face_recognition.face_encodings(rgb_frame, locations)
                coordinate_scale = 1.0
            else:
                small = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locations = face_recognition.face_locations(rgb_small, model="hog")
                detector_scores = [None] * len(locations)
                encodings = face_recognition.face_encodings(rgb_small, locations)
                coordinate_scale = 1.0 / FRAME_SCALE

            for (top, right, bottom, left), encoding, detector_score in zip(
                locations, encodings, detector_scores
            ):
                candidate_id, distance, accepted = find_best_candidate(
                    known_encodings, known_ids, encoding
                )

                if accepted:
                    student_id = candidate_id
                    observed_since_checkpoint.add(student_id)
                    record_attendance(student_id, today, attended, detector_score, distance)
                    label = f"{student_id} - Present"
                    color = (0, 180, 0)
                else:
                    label = "Unknown"
                    color = (0, 0, 220)

                top, right, bottom, left = [
                    int(value * coordinate_scale) for value in (top, right, bottom, left)
                ]
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
                cv2.putText(frame, label, (left + 6, bottom - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            if session_id is not None and time.monotonic() >= next_checkpoint:
                checkpoint_at = datetime.now().replace(microsecond=0)
                stored = attendance_store.save_checkpoint(
                    session_id,
                    checkpoint_roster,
                    observed_since_checkpoint,
                    checkpoint_window_start,
                    checkpoint_at,
                )
                print(
                    f"Checkpoint saved for {len(checkpoint_roster)} students "
                    f"({stored} new rows); not-observed results require review."
                )
                observed_since_checkpoint.clear()
                checkpoint_window_start = checkpoint_at
                next_checkpoint = time.monotonic() + checkpoint_interval

            cv2.imshow("Attendance Recognition", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if session_id is not None:
            try:
                attendance_store.finish_class_session(session_id, datetime.now().replace(microsecond=0))
            except Exception as exc:
                print(f"Could not record the session end event: {exc}")
        data.close()


if __name__ == "__main__":
    main()
