"""Compare face-position and identity observations with an exam seat plan.

Outputs are review suggestions only. A model match or mismatch is never a final
seating decision.
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from seat_plan import load_plan, point_in_polygon


def finite_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def load_observations(path, plan):
    with Path(path).open("r", encoding="utf-8") as file:
        try:
            payload = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid observations JSON: {exc}") from exc
    return validate_observations(payload, plan)


def validate_observations(payload, plan):
    """Validate a decoded observation payload against the seat plan."""
    if not isinstance(payload, dict):
        raise ValueError("Observations document must be a JSON object.")
    if payload.get("exam_id") != plan["exam_id"]:
        raise ValueError("Observation exam_id does not match the seat plan.")
    frame = payload.get("frame")
    if not isinstance(frame, dict):
        raise ValueError("Observations must include frame width and height.")
    frame_width, frame_height = frame.get("width"), frame.get("height")
    if (
        not isinstance(frame_width, int)
        or isinstance(frame_width, bool)
        or not isinstance(frame_height, int)
        or isinstance(frame_height, bool)
    ):
        raise ValueError("Observation frame width and height must be integers.")
    if (frame_width, frame_height) != (
        plan["camera"]["frame_width"], plan["camera"]["frame_height"]
    ):
        raise ValueError("Observation frame dimensions do not match the seat plan.")
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations must be a JSON array.")

    width, height = frame["width"], frame["height"]
    validated = []
    for index, item in enumerate(observations, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Observation {index} must be an object.")
        box = item.get("bbox")
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(not finite_number(value) for value in box)
        ):
            raise ValueError(f"Observation {index} bbox must contain four finite pixel coordinates.")
        left, top, right, bottom = box
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError(f"Observation {index} bbox must be inside the declared frame.")

        identity_status = item.get("identity_status")
        candidate_student_id = item.get("candidate_student_id")
        if not isinstance(identity_status, str) or identity_status not in {"candidate", "unknown", "uncertain"}:
            raise ValueError(
                f"Observation {index} identity_status must be candidate, unknown, or uncertain."
            )
        if identity_status == "candidate":
            if not isinstance(candidate_student_id, str) or not candidate_student_id.strip():
                raise ValueError(f"Observation {index}: candidate identity requires candidate_student_id.")
            candidate_student_id = candidate_student_id.strip()
        elif candidate_student_id is not None:
            raise ValueError(f"Observation {index}: unknown/uncertain identities must not include candidate_student_id.")

        match_distance = item.get("match_distance")
        if match_distance is not None and (
            not finite_number(match_distance)
            or match_distance < 0
        ):
            raise ValueError(f"Observation {index}: match_distance must be a non-negative finite number.")
        validated.append({
            "bbox": [float(value) for value in box],
            "identity_status": identity_status,
            "candidate_student_id": candidate_student_id,
            "match_distance": match_distance,
        })
    return validated


def compare_observations(plan, observations):
    """Return per-seat review suggestions without asserting a violation."""
    seats = plan["seats"]
    width = plan["camera"]["frame_width"]
    height = plan["camera"]["frame_height"]
    by_seat = {seat["seat_id"]: [] for seat in seats}
    ambiguous_by_seat = Counter()
    outside_count = 0
    ambiguous_count = 0

    for index, observation in enumerate(observations, start=1):
        left, top, right, bottom = observation["bbox"]
        center = ((left + right) / (2 * width), (top + bottom) / (2 * height))
        matching = [seat for seat in seats if point_in_polygon(center, seat["zone"])]
        if len(matching) == 1:
            by_seat[matching[0]["seat_id"]].append((index, observation))
        elif len(matching) > 1:
            ambiguous_count += 1
            for seat in matching:
                ambiguous_by_seat[seat["seat_id"]] += 1
        else:
            outside_count += 1

    detected_ids = Counter(
        item["candidate_student_id"]
        for item in observations
        if item["identity_status"] == "candidate"
    )
    rows = []
    status_counts = Counter()
    for seat in seats:
        seat_id = seat["seat_id"]
        expected_id = seat["student_id"]
        faces = by_seat[seat_id]
        ambiguous = ambiguous_by_seat[seat_id]
        observed_id = None
        if ambiguous:
            status = "uncertain"
            reason = "face position overlaps multiple seat zones"
        elif not faces:
            status = "uncertain"
            reason = "no unambiguous face detected in this zone; this does not establish an empty seat"
        elif len(faces) > 1:
            status = "uncertain"
            reason = "multiple face detections in one seat zone"
        else:
            _, face = faces[0]
            observed_id = face["candidate_student_id"]
            if face["identity_status"] != "candidate":
                status = "uncertain"
                reason = f"identity is {face['identity_status']}"
            elif detected_ids[observed_id] > 1:
                status = "uncertain"
                reason = "the same identity was reported in multiple detections"
            elif observed_id == expected_id:
                status = "candidate_match_for_review"
                reason = "candidate ID matches the assigned seat; teacher review is still required"
            else:
                status = "possible_assignment_mismatch_for_review"
                reason = "candidate ID differs from the seat assignment; review evidence before any action"
        status_counts[status] += 1
        rows.append({
            "seat_id": seat_id,
            "expected_student_id": expected_id,
            "candidate_student_id": observed_id,
            "status": status,
            "reason": reason,
            "review_required": True,
        })

    return {
        "exam_id": plan["exam_id"],
        "review_only": True,
        "face_observation_count": len(observations),
        "ambiguous_face_count": ambiguous_count,
        "outside_seat_zone_count": outside_count,
        "status_counts": dict(status_counts),
        "seats": rows,
        "disclaimer": "AI observations are not a seating decision. A teacher must review every result.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="local seat-plan JSON")
    parser.add_argument("--observations", type=Path, required=True, help="identity and bounding-box observation JSON")
    parser.add_argument("--output", type=Path, help="optional local JSON review report")
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error(f"output already exists; choose another path to avoid overwriting it: {args.output}")
    try:
        plan = load_plan(args.plan)
        observations = load_observations(args.observations, plan)
        result = compare_observations(plan, observations)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Exam: {result['exam_id']} | face observations: {result['face_observation_count']}")
    for status, count in sorted(result["status_counts"].items()):
        print(f"  {status}: {count}")
    print(
        f"Ambiguous positions: {result['ambiguous_face_count']} | "
        f"outside seat zones: {result['outside_seat_zone_count']}"
    )
    print(result["disclaimer"])

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(result, file, indent=2)
            file.write("\n")
        print(f"Saved local review report: {args.output}")


if __name__ == "__main__":
    main()
