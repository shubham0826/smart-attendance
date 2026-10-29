"""Shared CSV/MySQL storage interface used by recognition and reports."""

import csv
import os
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_DIR / "dataset"
ATTENDANCE_FILE = PROJECT_DIR / "attendance.csv"


def backend():
    from database.config import load_local_environment

    load_local_environment()
    value = os.environ.get("ATTENDANCE_STORAGE", "csv").strip().lower()
    if value not in {"csv", "mysql"}:
        raise RuntimeError("ATTENDANCE_STORAGE must be either 'csv' or 'mysql'.")
    return value


def csv_roster():
    return sorted(path.name for path in DATASET_DIR.iterdir() if path.is_dir()) if DATASET_DIR.is_dir() else []


def read_csv_attendance(path=ATTENDANCE_FILE):
    """Read and validate attendance rows using the project's CSV format."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Attendance log not found: {path}")
    rows = []
    seen = set()
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "time", "student_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Attendance CSV is missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            student_id = (row.get("student_id") or "").strip()
            date_text = (row.get("date") or "").strip()
            time_text = (row.get("time") or "").strip()
            try:
                day = datetime.strptime(date_text, "%Y-%m-%d").date()
                check_in = datetime.strptime(time_text, "%H:%M:%S").time()
            except ValueError as exc:
                raise ValueError(f"Invalid date, time, or student ID on CSV line {line_number}.") from exc
            if not student_id or day.isoformat() != date_text or check_in.strftime("%H:%M:%S") != time_text:
                raise ValueError(f"Invalid date, time, or student ID on CSV line {line_number}.")
            key = (student_id, day)
            if key in seen:
                raise ValueError(f"Duplicate check-in for {student_id} on {day.isoformat()}.")
            seen.add(key)
            rows.append({"student_id": student_id, "attendance_date": day, "check_in_time": check_in})
    return rows


def list_students(active_only=True):
    if backend() == "mysql":
        from database.mysql_repository import list_students as mysql_list_students

        return mysql_list_students(active_only=active_only)
    return csv_roster()


def list_attendance(start_date=None, end_date=None):
    if backend() == "mysql":
        from database.mysql_repository import list_attendance as mysql_list_attendance

        return mysql_list_attendance(start_date=start_date, end_date=end_date)
    if not ATTENDANCE_FILE.is_file():
        return []
    rows = read_csv_attendance()
    if start_date is not None:
        rows = [row for row in rows if row["attendance_date"] >= start_date]
    if end_date is not None:
        rows = [row for row in rows if row["attendance_date"] <= end_date]
    return [
        {**row, "check_in_time": row["check_in_time"].strftime("%H:%M:%S")}
        for row in rows
    ]


def record_check_in(student_id, attendance_date, check_in_time, detector_score=None, match_distance=None):
    if backend() == "mysql":
        from database.mysql_repository import record_check_in as mysql_record_check_in

        return mysql_record_check_in(
            student_id, attendance_date, check_in_time, detector_score, match_distance
        )

    if any(row["student_id"] == student_id and row["attendance_date"] == attendance_date
           for row in list_attendance(attendance_date, attendance_date)):
        return False
    ATTENDANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not ATTENDANCE_FILE.exists() or ATTENDANCE_FILE.stat().st_size == 0
    with ATTENDANCE_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if needs_header:
            writer.writerow(["date", "time", "student_id"])
        writer.writerow([attendance_date.isoformat(), check_in_time.strftime("%H:%M:%S"), student_id])
    return True


def start_class_session(session_label, checkpoint_interval_minutes):
    if backend() != "mysql":
        raise RuntimeError("Periodic checkpoint storage currently requires ATTENDANCE_STORAGE=mysql.")
    from database.mysql_repository import create_class_session

    return create_class_session(session_label, checkpoint_interval_minutes)


def finish_class_session(session_id, event_at):
    if backend() != "mysql":
        raise RuntimeError("Periodic checkpoint storage currently requires ATTENDANCE_STORAGE=mysql.")
    from database.mysql_repository import end_class_session

    return end_class_session(session_id, event_at)


def save_checkpoint(session_id, student_ids, observed_ids, window_start_at, checkpoint_at):
    if backend() != "mysql":
        raise RuntimeError("Periodic checkpoint storage currently requires ATTENDANCE_STORAGE=mysql.")
    from database.mysql_repository import record_checkpoint

    return record_checkpoint(session_id, student_ids, observed_ids, window_start_at, checkpoint_at)


def list_checkpoint_observations(session_id=None):
    if backend() != "mysql":
        raise RuntimeError("Periodic checkpoint storage currently requires ATTENDANCE_STORAGE=mysql.")
    from database.mysql_repository import list_checkpoint_observations as mysql_list_checkpoints

    return mysql_list_checkpoints(session_id)
