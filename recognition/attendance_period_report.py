"""Export per-student attendance totals for a date range from the CSV log."""

import argparse
import csv
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_DIR / "dataset"
ATTENDANCE_FILE = PROJECT_DIR / "attendance.csv"
REPORT_DIR = PROJECT_DIR / "reports"


def parse_date(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format")
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start_date", type=parse_date, help="first date, inclusive (YYYY-MM-DD)")
    parser.add_argument("end_date", type=parse_date, help="last date, inclusive (YYYY-MM-DD)")
    parser.add_argument("--input", type=Path, default=ATTENDANCE_FILE, help="attendance CSV")
    parser.add_argument("--output", type=Path, help="optional CSV output path")
    args = parser.parse_args()

    if args.end_date < args.start_date:
        parser.error("end_date must be on or after start_date")
    if not DATASET_DIR.is_dir():
        raise SystemExit(f"Roster directory not found: {DATASET_DIR}")
    roster = sorted(path.name for path in DATASET_DIR.iterdir() if path.is_dir())
    if not roster:
        raise SystemExit(f"No student folders found in {DATASET_DIR}")
    if not args.input.is_file():
        raise SystemExit(f"Attendance log not found: {args.input}")

    present_dates = {student_id: set() for student_id in roster}
    first_seen = {}
    last_seen = {}
    class_dates = set()
    with args.input.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "time", "student_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Attendance CSV is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            student_id = (row.get("student_id") or "").strip()
            try:
                day = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
                check_in = datetime.strptime((row.get("time") or "").strip(), "%H:%M:%S").time()
            except ValueError:
                continue
            if day.isoformat() != (row.get("date") or "").strip():
                continue
            if not args.start_date <= day <= args.end_date or student_id not in present_dates:
                continue
            day_text = day.isoformat()
            time_text = check_in.strftime("%H:%M:%S")
            present_dates[student_id].add(day_text)
            class_dates.add(day_text)
            first_seen[student_id] = min(first_seen.get(student_id, time_text), time_text)
            last_seen[student_id] = max(last_seen.get(student_id, time_text), time_text)

    observed_days = len(class_dates)
    rows = []
    for student_id in roster:
        days_present = len(present_dates[student_id])
        rows.append({
            "student_id": student_id,
            "logged_class_days": observed_days,
            "days_present": days_present,
            "days_absent": max(observed_days - days_present, 0),
            "attendance_percent": f"{(100 * days_present / observed_days):.1f}" if observed_days else "",
            "first_check_in": first_seen.get(student_id, ""),
            "last_check_in": last_seen.get(student_id, ""),
        })

    args.output = args.output or REPORT_DIR / (
        f"attendance_summary_{args.start_date.isoformat()}_{args.end_date.isoformat()}.csv"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["student_id", "logged_class_days", "days_present", "days_absent", "attendance_percent", "first_check_in", "last_check_in"]
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Period: {args.start_date.isoformat()} through {args.end_date.isoformat()}")
    print(f"Logged attendance dates in range: {observed_days}")
    print(f"Students in roster: {len(roster)}")
    print(f"Saved period summary: {args.output}")
    if not observed_days:
        print("No valid attendance dates were recorded in this range; attendance percentages are blank.")


if __name__ == "__main__":
    main()
