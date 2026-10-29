"""Draw normalized seat zones on a still frame and create a local exam plan."""

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from exam.seat_plan import validate_plan


def load_assignments(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Seat assignment CSV not found: {path}")
    assignments = []
    seen_seats, seen_students = set(), set()
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"seat_id", "student_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Assignment CSV is missing columns: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            seat_id = (row.get("seat_id") or "").strip()
            student_id = (row.get("student_id") or "").strip()
            if not seat_id or not student_id:
                raise ValueError(f"Both seat_id and student_id are required on CSV row {row_number}.")
            if seat_id in seen_seats:
                raise ValueError(f"Duplicate seat_id {seat_id!r} on CSV row {row_number}.")
            if student_id in seen_students:
                raise ValueError(f"Student {student_id!r} is assigned more than once.")
            seen_seats.add(seat_id)
            seen_students.add(student_id)
            assignments.append({"seat_id": seat_id, "student_id": student_id})
    if not assignments:
        raise ValueError("Assignment CSV must contain at least one seat.")
    return assignments


def draw_preview(frame, width, height, seats, current_points, active_seat):
    original_height, original_width = frame.shape[:2]
    preview = cv2.resize(frame, (width, height))
    for seat in seats:
        polygon = np.array(
            [[round(x * width), round(y * height)] for x, y in seat["zone"]],
            dtype=np.int32,
        )
        cv2.polylines(preview, [polygon], True, (0, 180, 0), 2)
        x, y = polygon[0]
        cv2.putText(preview, seat["seat_id"], (int(x), max(20, int(y) - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 0), 2)

    for point in current_points:
        cv2.circle(preview, point, 5, (0, 190, 255), -1)
    if len(current_points) > 1:
        cv2.polylines(preview, [np.array(current_points, dtype=np.int32)], False, (0, 190, 255), 2)
    instruction = f"Seat {active_seat}: click zone corners | Enter=finish | Backspace=undo | Esc=cancel"
    cv2.rectangle(preview, (0, 0), (width, 34), (20, 30, 40), -1)
    cv2.putText(preview, instruction, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)
    return preview


def draw_zone(frame, assignment, seats, preview_size):
    original_height, original_width = frame.shape[:2]
    max_width, max_height = preview_size
    scale = min(max_width / original_width, max_height / original_height, 1.0)
    preview_width = max(1, round(original_width * scale))
    preview_height = max(1, round(original_height * scale))
    points = []
    window = "Seat-zone calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, preview_width, preview_height)
    cv2.setMouseCallback(window, lambda event, x, y, flags, userdata: points.append((x, y)) if event == cv2.EVENT_LBUTTONDOWN else None)
    try:
        while True:
            preview = draw_preview(frame, preview_width, preview_height, seats, points, assignment["seat_id"])
            cv2.imshow(window, preview)
            key = cv2.waitKey(20) & 0xFF
            if key == 27:
                raise SystemExit("Seat-zone calibration canceled; no plan was written.")
            if key in (8, 127):
                if points:
                    points.pop()
            elif key in (10, 13):
                if len(points) < 3:
                    print(f"Seat {assignment['seat_id']}: click at least three distinct corners.")
                    continue
                zone = [[round(x / preview_width, 7), round(y / preview_height, 7)] for x, y in points]
                candidate = {
                    "exam_id": "CALIBRATION_PREVIEW",
                    "camera": {"frame_width": original_width, "frame_height": original_height},
                    "seats": seats + [{**assignment, "zone": zone}],
                }
                try:
                    validate_plan(candidate)
                except ValueError as exc:
                    print(f"Seat {assignment['seat_id']}: {exc} Draw this zone again.")
                    points.clear()
                    continue
                return zone
    finally:
        cv2.destroyWindow(window)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="reference frame from the exam camera")
    parser.add_argument("--assignments", type=Path, required=True, help="CSV containing seat_id,student_id columns")
    parser.add_argument("--exam-id", required=True, help="approved exam identifier")
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "exam" / "seat_plan.local.json")
    parser.add_argument("--preview-width", type=int, default=1200)
    parser.add_argument("--preview-height", type=int, default=760)
    args = parser.parse_args()
    if args.preview_width < 1 or args.preview_height < 1:
        parser.error("preview dimensions must be positive")
    if args.output.exists():
        parser.error(f"output already exists; choose another path to avoid overwriting it: {args.output}")

    try:
        assignments = load_assignments(args.assignments)
        frame = cv2.imread(str(args.image))
        if frame is None:
            raise ValueError(f"Could not read reference frame: {args.image}")
        height, width = frame.shape[:2]
        seats = []
        for assignment in assignments:
            zone = draw_zone(
                frame,
                assignment,
                seats,
                (args.preview_width, args.preview_height),
            )
            seats.append({**assignment, "zone": zone})
        plan = validate_plan({
            "exam_id": args.exam_id,
            "camera": {"frame_width": width, "frame_height": height},
            "seats": seats,
        })
        output_payload = {
            "exam_id": plan["exam_id"],
            "camera": plan["camera"],
            "seats": [
                {"seat_id": seat["seat_id"], "student_id": seat["student_id"], "zone": seat["zone"]}
                for seat in plan["seats"]
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(output_payload, file, indent=2)
            file.write("\n")
    except (OSError, ValueError, cv2.error) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Seat plan created: {args.output}")
    print(f"Exam: {args.exam_id} | Seats: {len(seats)} | Camera frame: {width}x{height}")
    print("The image was used only to draw zones; it was not copied or saved.")


if __name__ == "__main__":
    main()
