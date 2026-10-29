"""Register the local roster and optionally import the CSV attendance log."""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database import attendance_store, mysql_repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--import-csv",
        action="store_true",
        help="also import attendance.csv (safe to rerun; existing daily rows are skipped)",
    )
    parser.add_argument("--attendance", type=Path, default=attendance_store.ATTENDANCE_FILE)
    args = parser.parse_args()

    connection = mysql_repository.connect_from_environment()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT MAX(version_id) FROM schema_version")
        version = cursor.fetchone()[0]
    finally:
        connection.close()
    if version != 2:
        raise SystemExit("MySQL schema version 2 is missing. Run database/migrations/002_checkpoints.sql first.")

    roster = attendance_store.csv_roster()
    if not roster:
        raise SystemExit(
            f"No local student folders found in {attendance_store.DATASET_DIR}; "
            "enroll or restore the roster before initializing MySQL."
        )
    inserted_students = mysql_repository.sync_students(roster)
    print(f"Roster synchronized: {len(roster)} IDs ({inserted_students} newly added).")

    if args.import_csv:
        existing = set(mysql_repository.list_students(active_only=False))
        csv_rows = attendance_store.read_csv_attendance(args.attendance)
        missing = sorted({row["student_id"] for row in csv_rows} - existing)
        if missing:
            raise SystemExit(
                "CSV contains student IDs absent from the MySQL roster. Review the roster before importing."
            )
        inserted, skipped = mysql_repository.import_attendance_csv(args.attendance)
        print(f"CSV import complete: {inserted} inserted, {skipped} already present.")
    else:
        print("Attendance CSV was not imported. Pass --import-csv after reviewing it to migrate existing records.")


if __name__ == "__main__":
    main()
