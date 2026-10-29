"""Check attendance.csv for invalid rows and duplicate daily check-ins."""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database import attendance_store


DEFAULT_LOG = PROJECT_DIR / "attendance.csv"
DEFAULT_REPORT = PROJECT_DIR / "reports" / "attendance_audit.csv"
REQUIRED_COLUMNS = {"date", "time", "student_id"}


def audit(path, roster):
    if not path.is_file():
        raise SystemExit(f"Attendance log not found: {path}")

    issues = []
    seen = set()
    rows_read = 0
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        headers = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - headers)
        if missing:
            raise SystemExit(f"Attendance log is missing required columns: {', '.join(missing)}")

        for line_number, row in enumerate(reader, start=2):
            rows_read += 1
            student_id = (row.get("student_id") or "").strip()
            attendance_date = (row.get("date") or "").strip()
            attendance_time = (row.get("time") or "").strip()
            row_issues = []

            try:
                datetime.strptime(attendance_date, "%Y-%m-%d")
            except ValueError:
                row_issues.append("invalid_date")
            try:
                datetime.strptime(attendance_time, "%H:%M:%S")
            except ValueError:
                row_issues.append("invalid_time")
            if not student_id:
                row_issues.append("missing_student_id")
            elif student_id not in roster:
                row_issues.append("student_not_in_roster")

            key = (attendance_date, student_id)
            if student_id and key in seen:
                row_issues.append("duplicate_daily_check_in")
            if student_id:
                seen.add(key)

            if row.get(None):
                row_issues.append("extra_columns")
            if row_issues:
                issues.append({
                    "line_number": line_number,
                    "issues": ";".join(row_issues),
                    "date": attendance_date,
                    "time": attendance_time,
                    "student_id": student_id,
                })
    return rows_read, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="inspect this CSV instead of the configured backend")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="CSV file for rows with issues")
    parser.add_argument("--strict", action="store_true", help="return exit code 1 if any issues are found")
    args = parser.parse_args()

    roster = set(attendance_store.list_students(active_only=False))
    if args.input or attendance_store.backend() == "csv":
        rows_read, issues = audit(args.input or DEFAULT_LOG, roster)
    else:
        records = attendance_store.list_attendance()
        rows_read = len(records)
        issues = []
        seen = set()
        for row_number, row in enumerate(records, start=1):
            student_id = row["student_id"]
            attendance_date = row["attendance_date"].isoformat()
            attendance_time = str(row["check_in_time"])
            row_issues = []
            if not student_id:
                row_issues.append("missing_student_id")
            elif student_id not in roster:
                row_issues.append("student_not_in_roster")
            key = (attendance_date, student_id)
            if student_id and key in seen:
                row_issues.append("duplicate_daily_check_in")
            if student_id:
                seen.add(key)
            if row_issues:
                issues.append({
                    "line_number": row_number,
                    "issues": ";".join(row_issues),
                    "date": attendance_date,
                    "time": attendance_time,
                    "student_id": student_id,
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["line_number", "issues", "date", "time", "student_id"])
        writer.writeheader()
        writer.writerows(issues)

    print(f"Attendance rows checked: {rows_read}")
    print(f"Rows with issues: {len(issues)}")
    for issue in issues:
        print(f"  line {issue['line_number']}: {issue['issues']}")
    print(f"Audit details: {args.output}")
    return 1 if args.strict and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
