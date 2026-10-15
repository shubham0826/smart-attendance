"""Export the current roster and attendance CSV as a validated MySQL import."""

import argparse
import csv
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ROSTER = PROJECT_DIR / "dataset"
DEFAULT_ATTENDANCE = PROJECT_DIR / "attendance.csv"
DEFAULT_OUTPUT = PROJECT_DIR / "reports" / "smart_attendance_import.sql"


def sql_string(value):
    """Quote a string literal for MySQL's default backslash escape mode."""
    return "'" + value.replace("\\", "\\\\").replace("'", "''").replace("\0", "\\0") + "'"


def load_rows(roster_dir, attendance_file):
    if not roster_dir.is_dir():
        raise SystemExit(f"Roster directory not found: {roster_dir}")
    roster = sorted(path.name for path in roster_dir.iterdir() if path.is_dir())
    if not roster:
        raise SystemExit("No student folders found in the roster directory.")
    if not attendance_file.is_file():
        raise SystemExit(f"Attendance CSV not found: {attendance_file}")

    attendance_rows = []
    seen = set()
    with attendance_file.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "time", "student_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Attendance CSV is missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            student_id = (row.get("student_id") or "").strip()
            attendance_date = (row.get("date") or "").strip()
            check_in_time = (row.get("time") or "").strip()
            try:
                parsed_date = datetime.strptime(attendance_date, "%Y-%m-%d")
                parsed_time = datetime.strptime(check_in_time, "%H:%M:%S")
            except ValueError as exc:
                raise SystemExit(f"Invalid date or time on CSV line {line_number}: {exc}") from exc
            if parsed_date.strftime("%Y-%m-%d") != attendance_date:
                raise SystemExit(f"Date must use YYYY-MM-DD format on CSV line {line_number}.")
            if parsed_time.strftime("%H:%M:%S") != check_in_time:
                raise SystemExit(f"Time must use HH:MM:SS format on CSV line {line_number}.")
            if student_id not in roster:
                raise SystemExit(f"Student {student_id!r} on line {line_number} is not in the roster.")
            key = (attendance_date, student_id)
            if key in seen:
                raise SystemExit(f"Duplicate daily check-in for {student_id} on {attendance_date}.")
            seen.add(key)
            attendance_rows.append((attendance_date, check_in_time, student_id))
    return roster, attendance_rows


def build_sql(roster, attendance_rows):
    statements = [
        "-- Generated from the local roster and attendance.csv. Review before import.",
        "-- Run database/schema.sql first. This file does not contain face images or embeddings.",
        "USE smart_attendance;",
        "START TRANSACTION;",
    ]
    for student_id in roster:
        statements.append(
            "INSERT INTO students (student_id) VALUES "
            f"({sql_string(student_id)});"
        )
    for attendance_date, check_in_time, student_id in attendance_rows:
        statements.append(
            "INSERT INTO attendance (student_id, attendance_date, check_in_time) VALUES "
            f"({sql_string(student_id)}, '{attendance_date}', '{check_in_time}');"
        )
    statements.extend(["COMMIT;", ""])
    return "\n".join(statements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--attendance", type=Path, default=DEFAULT_ATTENDANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    roster, attendance_rows = load_rows(args.roster, args.attendance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_sql(roster, attendance_rows), encoding="utf-8")
    print(f"Import SQL created: {args.output}")
    print(f"Students: {len(roster)} | Attendance rows: {len(attendance_rows)}")
    print("No source files were changed. Apply only after schema.sql, and do not rerun after a successful import.")


if __name__ == "__main__":
    main()
