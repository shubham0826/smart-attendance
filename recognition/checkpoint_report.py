"""Export review-only checkpoint observations for one MySQL class session."""

import argparse
import csv
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database import attendance_store


DEFAULT_OUTPUT_DIR = PROJECT_DIR / "reports"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", type=int, help="session ID (defaults to the latest session)")
    parser.add_argument("--output", type=Path, help="optional CSV output path")
    args = parser.parse_args()
    if args.session_id is not None and args.session_id < 1:
        parser.error("--session-id must be positive")

    session_id, rows = attendance_store.list_checkpoint_observations(args.session_id)
    if session_id is None:
        raise SystemExit("No class sessions have been recorded yet.")

    output = args.output or DEFAULT_OUTPUT_DIR / f"checkpoint_session_{session_id}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "session_id",
        "student_id",
        "window_start_at",
        "checkpoint_at",
        "observation_status",
        "review_status",
    ]
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **row,
                "window_start_at": row["window_start_at"].isoformat(sep=" "),
                "checkpoint_at": row["checkpoint_at"].isoformat(sep=" "),
            })

    not_observed = sum(row["observation_status"] == "not_observed" for row in rows)
    pending = sum(row["review_status"] == "pending" for row in rows)
    print(f"Session: {session_id} | Checkpoint rows: {len(rows)}")
    print(f"Not observed (requires human review): {not_observed} | Pending review: {pending}")
    print(f"Saved checkpoint report: {output}")


if __name__ == "__main__":
    main()
