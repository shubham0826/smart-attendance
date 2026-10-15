"""Run a leave-one-out sanity check on saved face embeddings.

This is not an independent accuracy test: nearby frames from the same
enrollment session may be near duplicates, and no unknown faces are included.
"""

import csv
from pathlib import Path

import face_recognition
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent.parent
EMBEDDINGS_FILE = Path(__file__).resolve().parent / "face_embeddings.npz"
REPORT_DIR = PROJECT_DIR / "reports" / "matching_evaluation"
THRESHOLDS = tuple(round(value, 2) for value in np.arange(0.30, 0.701, 0.05))


def main():
    if not EMBEDDINGS_FILE.is_file() or EMBEDDINGS_FILE.stat().st_size == 0:
        raise SystemExit(f"Embeddings not found: {EMBEDDINGS_FILE}")

    with np.load(EMBEDDINGS_FILE, allow_pickle=False) as data:
        encodings = data["encodings"].astype(np.float64)
        student_ids = data["names"].astype(str)

    if encodings.ndim != 2 or len(encodings) != len(student_ids) or not len(encodings):
        raise SystemExit("Embedding file is empty or inconsistent.")
    if len(set(student_ids)) < 2:
        raise SystemExit("At least two enrolled identities are needed for this check.")

    probes = []
    for index, (encoding, expected_id) in enumerate(zip(encodings, student_ids)):
        keep = np.arange(len(encodings)) != index
        if not np.any(student_ids[keep] == expected_id):
            continue
        distances = face_recognition.face_distance(encodings[keep], encoding)
        candidate_ids = student_ids[keep]
        best = int(np.argmin(distances))
        probes.append((expected_id, candidate_ids[best], float(distances[best])))

    rows = []
    for threshold in THRESHOLDS:
        correct = wrong_accepted = rejected = 0
        for expected_id, predicted_id, distance in probes:
            if distance > threshold:
                rejected += 1
            elif predicted_id == expected_id:
                correct += 1
            else:
                wrong_accepted += 1
        rows.append((threshold, correct, wrong_accepted, rejected, len(probes)))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "threshold_sweep.csv"
    with report_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["threshold", "correctly_recognized", "wrong_identity_accepted", "rejected", "total_probes"])
        writer.writerows(rows)

    print(f"Leave-one-out probes: {len(probes)} across {len(set(student_ids))} enrolled IDs")
    print("Threshold | Correct | Wrong accepted | Rejected | Total")
    for threshold, correct, wrong, rejected, total in rows:
        print(f"{threshold:9.2f} | {correct:7d} | {wrong:14d} | {rejected:8d} | {total:5d}")
    print(f"Threshold report: {report_path}")
    print("Interpretation limits: same-session enrollment samples; no unknown-person probes; not a validated attendance threshold.")


if __name__ == "__main__":
    main()
