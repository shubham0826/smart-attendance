"""Optional MySQL repository for the Smart Attendance schema.

This module is deliberately not connected to the recognition flow yet. The CSV
backend remains active until a local MySQL server is configured and verified.
"""

import os


def connect_from_environment():
    """Open a MySQL connection using ATTENDANCE_DB_* environment variables."""
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "MySQL Connector/Python is required for the optional MySQL backend. "
            'Install it with: python -m pip install "mysql-connector-python==9.5.0"'
        ) from exc

    user = os.environ.get("ATTENDANCE_DB_USER")
    password = os.environ.get("ATTENDANCE_DB_PASSWORD")
    if not user or password is None:
        raise RuntimeError("Set ATTENDANCE_DB_USER and ATTENDANCE_DB_PASSWORD in the environment.")
    try:
        port = int(os.environ.get("ATTENDANCE_DB_PORT", "3306"))
    except ValueError as exc:
        raise RuntimeError("ATTENDANCE_DB_PORT must be an integer.") from exc

    return mysql.connector.connect(
        host=os.environ.get("ATTENDANCE_DB_HOST", "127.0.0.1"),
        port=port,
        user=user,
        password=password,
        database=os.environ.get("ATTENDANCE_DB_NAME", "smart_attendance"),
        connection_timeout=5,
    )


def list_students(active_only=True):
    """Return the student IDs registered in MySQL."""
    connection = connect_from_environment()
    try:
        cursor = connection.cursor()
        query = "SELECT student_id FROM students"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY student_id"
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def list_attendance(start_date=None, end_date=None):
    """Return attendance rows, optionally restricted to an inclusive date range."""
    if start_date and end_date and end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    connection = connect_from_environment()
    try:
        cursor = connection.cursor(dictionary=True)
        query = (
            "SELECT student_id, attendance_date, check_in_time, detector_score, "
            "match_distance, source FROM attendance"
        )
        filters = []
        params = []
        if start_date is not None:
            filters.append("attendance_date >= %s")
            params.append(start_date)
        if end_date is not None:
            filters.append("attendance_date <= %s")
            params.append(end_date)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY attendance_date, check_in_time, student_id"
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    finally:
        connection.close()


def has_checked_in(student_id, attendance_date):
    """Check the current once-per-day attendance rule."""
    connection = connect_from_environment()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT 1 FROM attendance WHERE student_id = %s AND attendance_date = %s LIMIT 1",
            (student_id, attendance_date),
        )
        return cursor.fetchone() is not None
    finally:
        connection.close()


def record_check_in(student_id, attendance_date, check_in_time, detector_score=None, match_distance=None):
    """Insert one daily check-in; return False when that student already checked in."""
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "MySQL Connector/Python is required for the optional MySQL backend. "
            'Install it with: python -m pip install "mysql-connector-python==9.5.0"'
        ) from exc

    connection = connect_from_environment()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO attendance "
            "(student_id, attendance_date, check_in_time, detector_score, match_distance, source) "
            "VALUES (%s, %s, %s, %s, %s, 'face')",
            (student_id, attendance_date, check_in_time, detector_score, match_distance),
        )
        connection.commit()
        return True
    except mysql.connector.IntegrityError as exc:
        connection.rollback()
        if exc.errno == 1062:
            return False
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
