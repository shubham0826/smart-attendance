"""Validate exam seat plans and map face boxes to configured seat zones.

Seat-zone matching reports geometry only. It does not identify people or decide
whether a student violated an exam seating rule.
"""

import argparse
import json
import math
from pathlib import Path


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, point):
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        and abs(_orientation(a, b, point)) < 1e-10
    )


def _segments_intersect(a, b, c, d):
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if ((o1 > 0 > o2) or (o2 > 0 > o1)) and ((o3 > 0 > o4) or (o4 > 0 > o3)):
        return True
    return (
        (abs(o1) < 1e-10 and _on_segment(a, b, c))
        or (abs(o2) < 1e-10 and _on_segment(a, b, d))
        or (abs(o3) < 1e-10 and _on_segment(c, d, a))
        or (abs(o4) < 1e-10 and _on_segment(c, d, b))
    )


def _validate_polygon(zone, label):
    if not isinstance(zone, list) or len(zone) < 3:
        raise ValueError(f"{label}: zone must contain at least three [x, y] points.")
    points = []
    for point in zone:
        if not isinstance(point, list) or len(point) != 2 or not all(_number(value) for value in point):
            raise ValueError(f"{label}: each zone point must contain two finite numbers.")
        x, y = point
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError(f"{label}: zone coordinates must be normalized between 0 and 1.")
        points.append((float(x), float(y)))
    if len(set(points)) < 3:
        raise ValueError(f"{label}: zone must contain at least three distinct points.")

    doubled_area = sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )
    if abs(doubled_area) < 1e-10:
        raise ValueError(f"{label}: zone area must be greater than zero.")

    edge_count = len(points)
    for first in range(edge_count):
        a, b = points[first], points[(first + 1) % edge_count]
        for second in range(first + 1, edge_count):
            if second == first or second == (first + 1) % edge_count or first == (second + 1) % edge_count:
                continue
            c, d = points[second], points[(second + 1) % edge_count]
            if _segments_intersect(a, b, c, d):
                raise ValueError(f"{label}: zone polygon edges must not cross or overlap.")
    return points


def validate_plan(plan):
    """Validate a plan dictionary and return a normalized internal copy."""
    if not isinstance(plan, dict):
        raise ValueError("Seat plan must be a JSON object.")
    exam_id = plan.get("exam_id")
    if not isinstance(exam_id, str) or not exam_id.strip():
        raise ValueError("exam_id must be a non-empty string.")
    camera = plan.get("camera")
    if not isinstance(camera, dict):
        raise ValueError("camera must define frame_width and frame_height.")
    width, height = camera.get("frame_width"), camera.get("frame_height")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise ValueError("camera.frame_width must be a positive integer.")
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        raise ValueError("camera.frame_height must be a positive integer.")

    seats = plan.get("seats")
    if not isinstance(seats, list) or not seats:
        raise ValueError("seats must contain at least one assigned seat.")
    seat_ids, student_ids = set(), set()
    normalized_seats = []
    for index, seat in enumerate(seats, start=1):
        if not isinstance(seat, dict):
            raise ValueError(f"seats[{index - 1}] must be an object.")
        seat_id = seat.get("seat_id")
        student_id = seat.get("student_id")
        if not isinstance(seat_id, str) or not seat_id.strip():
            raise ValueError(f"seats[{index - 1}].seat_id must be a non-empty string.")
        if not isinstance(student_id, str) or not student_id.strip():
            raise ValueError(f"seat {seat_id!r}: student_id must be a non-empty string.")
        if seat_id in seat_ids:
            raise ValueError(f"Duplicate seat_id: {seat_id}.")
        if student_id in student_ids:
            raise ValueError(f"Student {student_id} is assigned to more than one seat.")
        seat_ids.add(seat_id)
        student_ids.add(student_id)
        normalized_seats.append({
            "seat_id": seat_id,
            "student_id": student_id,
            "zone": _validate_polygon(seat.get("zone"), f"seat {seat_id!r}"),
        })

    return {
        "exam_id": exam_id.strip(),
        "camera": {"frame_width": width, "frame_height": height},
        "seats": normalized_seats,
    }


def load_plan(path):
    with Path(path).open("r", encoding="utf-8") as file:
        try:
            return validate_plan(json.load(file))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in seat plan: {exc}") from exc


def point_in_polygon(point, polygon):
    """Return True when a normalized point is inside or on a seat-zone edge."""
    inside = False
    x, y = point
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(first, second, (x, y)):
            return True
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def map_face_boxes_to_seats(plan, boxes):
    """Count face-box centers in seat zones without making identity claims.

    `boxes` must contain `(left, top, right, bottom)` pixel coordinates for the
    frame dimensions declared by the seat plan.
    """
    valid = validate_plan(plan)
    width = valid["camera"]["frame_width"]
    height = valid["camera"]["frame_height"]
    counts = {seat["seat_id"]: 0 for seat in valid["seats"]}
    ambiguous_by_seat = {seat["seat_id"]: 0 for seat in valid["seats"]}
    ambiguous, unassigned = 0, 0
    for index, box in enumerate(boxes, start=1):
        if not isinstance(box, (tuple, list)) or len(box) != 4 or not all(_number(value) for value in box):
            raise ValueError(f"Face box {index} must contain four finite pixel coordinates.")
        left, top, right, bottom = box
        if right <= left or bottom <= top:
            raise ValueError(f"Face box {index} must have positive width and height.")
        center = ((left + right) / (2 * width), (top + bottom) / (2 * height))
        matching = [seat["seat_id"] for seat in valid["seats"] if point_in_polygon(center, seat["zone"])]
        if len(matching) == 1:
            counts[matching[0]] += 1
        elif len(matching) > 1:
            ambiguous += 1
            for seat_id in matching:
                ambiguous_by_seat[seat_id] += 1
        else:
            unassigned += 1

    observations = []
    for seat in valid["seats"]:
        count = counts[seat["seat_id"]]
        ambiguous_count = ambiguous_by_seat[seat["seat_id"]]
        observations.append({
            "seat_id": seat["seat_id"],
            "face_count": count,
            "ambiguous_face_count": ambiguous_count,
            "occupancy_observation": (
                "ambiguous_face_position" if ambiguous_count else
                "one_face_detected" if count == 1 else
                "multiple_faces_detected" if count > 1 else
                "no_face_detected"
            ),
        })
    return {
        "exam_id": valid["exam_id"],
        "seats": observations,
        "ambiguous_detection_count": ambiguous,
        "unassigned_detection_count": unassigned,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="JSON seating plan to validate")
    args = parser.parse_args()
    try:
        plan = load_plan(args.plan)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Seat plan valid: {plan['exam_id']}")
    print(f"Frame: {plan['camera']['frame_width']}x{plan['camera']['frame_height']}")
    print(f"Assigned seats: {len(plan['seats'])}")
    print("Geometry validation only; no people were identified or reviewed.")


if __name__ == "__main__":
    main()
