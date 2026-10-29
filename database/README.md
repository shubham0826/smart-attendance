# MySQL setup and attendance storage

Recognition, daily reports, period reports, and the offline dashboard can use
either the existing CSV files or MySQL. CSV remains the default. The database
stores student IDs and attendance records only; face images and embeddings stay
local and are not stored in MySQL.

## 1. Prepare MySQL

Start the local MySQL Server service. In MySQL Workbench, open and run
`schema.sql` as a MySQL administrator. It creates the `smart_attendance`
database and its version 2 tables. Create a dedicated application login rather
than using `root`; run the following after replacing the password with your own
strong password:

```sql
CREATE USER IF NOT EXISTS 'smart_attendance_app'@'127.0.0.1'
  IDENTIFIED BY 'replace_with_a_strong_password';
GRANT SELECT, INSERT ON smart_attendance.*
  TO 'smart_attendance_app'@'127.0.0.1';
```

For a database that already has schema version 1, open and run
`migrations/002_checkpoints.sql` as an administrator to add the checkpoint
tables and advance to schema version 2. The migration is safe to rerun.

The same project runs on the PC hosting MySQL. If MySQL is on another computer,
configure its bind address, firewall, and a host-restricted MySQL account before
using that server; do not expose port 3306 to the public internet.

## 2. Install the Python connector and set local settings

From PowerShell:

```powershell
cd "C:\smart attendance"
.\.venv\Scripts\python.exe -m pip install "mysql-connector-python==9.5.0"
Copy-Item .env.example .env
notepad .env
```

Set `ATTENDANCE_DB_PASSWORD` in `.env` to the password created above. Keep
`.env` private; Git ignores it. The application reads process environment
variables first and uses `.env` only for values not already set in the process.
Set `ATTENDANCE_STORAGE=mysql` only after the schema and account are ready.

## 3. Register the roster and optionally import existing attendance

The initializer checks the schema and adds IDs from local `dataset` folders to
the `students` table without changing existing names or active status:

```powershell
.\.venv\Scripts\python.exe .\database\initialize_mysql.py
```

This does not import the attendance CSV. Review the local CSV first, then opt in
to a one-time migration:

```powershell
.\.venv\Scripts\python.exe .\database\initialize_mysql.py --import-csv
```

The importer validates dates, times, and daily duplicates. It uses
`INSERT IGNORE`, so it can be rerun safely: existing student/day records are
skipped. The source CSV remains unchanged. To import another CSV, pass
`--attendance "C:\path\to\attendance.csv"`.

## 4. Use MySQL

Set `ATTENDANCE_STORAGE=mysql` in `.env`. Then run the usual commands:

```powershell
.\.venv\Scripts\python.exe .\recognition\recognize.py
.\.venv\Scripts\python.exe .\recognition\attendance_report.py
.\.venv\Scripts\python.exe .\recognition\attendance_period_report.py 2026-10-01 2026-10-31
.\.venv\Scripts\python.exe .\recognition\attendance_dashboard.py
.\.venv\Scripts\python.exe .\recognition\checkpoint_report.py
```

Recognition starts a class session and saves a summary of the preceding
observation window every 20 minutes by default. Use `--checkpoint-minutes N` to
change the interval. The checkpoint report marks students not seen during that
window as `not_observed` with review status `pending`; this is not an absence
decision. A teacher must review observations under the institution's attendance
policy.

Enrollment remains local. After adding new student folders, run
`database/initialize_mysql.py` again so their IDs are available to reports and
the attendance foreign key. Use `ATTENDANCE_STORAGE=csv` to return to the CSV
backend. You can set an explicit `--input` CSV for the period report or
dashboard without changing the selected backend.

The unique key `uq_attendance_student_day` allows one check-in per student per
day, matching the current prototype. Checkpoints are stored separately from
daily attendance. Recognition matching remains a prototype and needs independent
validation before attendance decisions rely on it.
