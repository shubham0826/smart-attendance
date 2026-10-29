"""Export per-student attendance totals for a date range from the CSV log."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database import attendance_store


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
    parser.add_argument("--input", type=Path, help="use this CSV instead of the configured backend")
    parser.add_argument("--output", type=Path, help="optional CSV output path")
    args = parser.parse_args()

    if args.end_date < args.start_date:
        parser.error("end_date must be on or after start_date")
    roster = attendance_store.list_students()
    if not roster:
        raise SystemExit("No registered students found in the configured attendance backend.")

    present_dates = {student_id: set() for student_id in roster}
    first_seen = {}
    last_seen = {}
    class_dates = set()
    if args.input:
        source_rows = attendance_store.read_csv_attendance(args.input)
    else:
        source_rows = attendance_store.list_attendance(args.start_date, args.end_date)
    for row in source_rows:
        student_id = row["student_id"]
        day = row["attendance_date"]
        check_in = row["check_in_time"]
        time_text = check_in if isinstance(check_in, str) else check_in.strftime("%H:%M:%S")
        if not args.start_date <= day <= args.end_date or student_id not in present_dates:
            continue
        day_text = day.isoformat()
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
