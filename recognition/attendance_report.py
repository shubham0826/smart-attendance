"""Print and export a daily attendance report.

Usage:
    python recognition/attendance_report.py
    python recognition/attendance_report.py 2026-10-15
"""

import argparse
from datetime import date, datetime
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database import attendance_store


REPORT_DIR = PROJECT_DIR / "reports"


def build_report(report_date):
    roster = attendance_store.list_students()
    if not roster:
        raise SystemExit("No registered students found in the configured attendance backend.")

    check_ins = {}
    for row in attendance_store.list_attendance(report_date, report_date):
        student_id = row["student_id"]
        if student_id not in roster:
            continue
        check_in = str(row["check_in_time"])
        if student_id not in check_ins or check_in < check_ins[student_id]:
            check_ins[student_id] = check_in

    return [
        {
            "date": report_date.isoformat(),
            "student_id": student_id,
            "status": "Present" if student_id in check_ins else "Absent",
            "check_in_time": check_ins.get(student_id, ""),
        }
        for student_id in roster
    ]


def main():
    parser = argparse.ArgumentParser(description="Create a daily report from the configured attendance backend")
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today().isoformat(),
        help="report date in YYYY-MM-DD format (defaults to today)",
    )
    args = parser.parse_args()
    try:
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        parser.error("date must use YYYY-MM-DD format")

    rows = build_report(report_date)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"attendance_{report_date.isoformat()}.csv"
    fieldnames = ["date", "student_id", "status", "check_in_time"]
    with report_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    present = [row for row in rows if row["status"] == "Present"]
    absent = [row["student_id"] for row in rows if row["status"] == "Absent"]
    print(f"Attendance report for {report_date.isoformat()}")
    print(f"Present: {len(present)} / {len(rows)}")
    for row in present:
        suffix = f" at {row['check_in_time']}" if row["check_in_time"] else ""
        print(f"  Present  {row['student_id']}{suffix}")
    for student_id in absent:
        print(f"  Absent   {student_id}")
    print(f"Saved report: {report_file}")


if __name__ == "__main__":
    main()
