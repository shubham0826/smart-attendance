"""Check MySQL settings and verify that the Smart Attendance schema is present."""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from database.config import load_local_environment


def main():
    load_local_environment()
    try:
        import mysql.connector
        from mysql.connector import Error
    except ImportError as exc:
        raise SystemExit(
            "MySQL Connector/Python is not installed. Run: "
            'python -m pip install "mysql-connector-python==9.5.0"'
        ) from exc

    host = os.environ.get("ATTENDANCE_DB_HOST", "127.0.0.1")
    user = os.environ.get("ATTENDANCE_DB_USER")
    password = os.environ.get("ATTENDANCE_DB_PASSWORD")
    database = os.environ.get("ATTENDANCE_DB_NAME", "smart_attendance")
    raw_port = os.environ.get("ATTENDANCE_DB_PORT", "3306")
    if not user or password is None:
        raise SystemExit(
            "Set ATTENDANCE_DB_USER and ATTENDANCE_DB_PASSWORD in the current "
            "PowerShell session. Credentials are read from environment variables, not source files."
        )
    try:
        port = int(raw_port)
    except ValueError:
        raise SystemExit("ATTENDANCE_DB_PORT must be an integer.")

    connection = None
    try:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connection_timeout=5,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        server_version = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(version_id) FROM schema_version")
        version = cursor.fetchone()[0]
        cursor.close()
        print(f"Connected to MySQL {server_version} at {host}:{port}/{database}")
        print(f"Attendance schema version: {version if version is not None else 'not recorded'}")
        if version != 2:
            print("Expected schema version 2. Run database/migrations/002_checkpoints.sql first.")
            return 1
        print("Smart Attendance schema is ready.")
        return 0
    except Error as exc:
        print(f"MySQL check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
