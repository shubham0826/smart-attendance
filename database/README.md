# MySQL storage foundation

`schema.sql` creates the first MySQL 8.0 schema for the prototype. Run it in
MySQL Workbench or the MySQL command line only after a local MySQL server is
installed and running. The project does not currently have a MySQL connection
configured, and the application continues to use `attendance.csv`.

After reviewing the CSV, generate a one-time SQL import file with:

```powershell
python "C:\smart attendance\database\export_mysql_import.py"
```

It validates dates, times, roster membership, and daily duplicates, then writes
`reports/smart_attendance_import.sql`. The current source exports five student
IDs and two attendance rows. In MySQL Workbench, run `schema.sql` first, then
open and run the generated import file. It is a one-time import; do not run it
again after it commits, because it intentionally uses ordinary inserts.

## Check the MySQL connection

The optional connection checker uses MySQL Connector/Python 9.5.0, which
supports this project's Python 3.13 environment. Install it with:

```powershell
python -m pip install "mysql-connector-python==9.5.0"
```

Set `ATTENDANCE_DB_HOST`, `ATTENDANCE_DB_PORT`, and `ATTENDANCE_DB_NAME` as
needed. For a password prompt in PowerShell, use a temporary credential object
in the current session:

```powershell
$env:ATTENDANCE_DB_USER = "smart_attendance_app"
$credential = Get-Credential -UserName $env:ATTENDANCE_DB_USER
$env:ATTENDANCE_DB_PASSWORD = $credential.GetNetworkCredential().Password
python "C:\smart attendance\database\check_connection.py"
Remove-Item Env:ATTENDANCE_DB_PASSWORD
```

The checker reports the MySQL server and schema version. It does not import the
SQL file or change attendance data.

`mysql_repository.py` contains optional parameterized operations to list
students, read attendance rows, check a daily mark, and write a check-in. It is
not wired into recognition or reporting; CSV remains the active backend. The
repository expects the schema and student rows to exist first. It has not been
run against a live MySQL server in this environment.

The schema stores student IDs, daily check-ins, and optional recognition scores.
It does not store face images or face embeddings. `uq_attendance_student_day`
enforces the current application rule of at most one attendance record per
student per day. If the handover's periodic checkpoint policy is adopted, that
key must be revised to include a session or checkpoint before database writes
are enabled.

## Safe rollout sequence

1. Install and secure MySQL 8.0 locally; create a dedicated application user
   rather than using the root account.
2. Open and run `schema.sql` in MySQL Workbench (or the MySQL CLI).
3. Populate `students` from the approved roster. Do not infer display names
   from folder names.
4. Back up the CSV log, generate the SQL import, and inspect it before importing.
5. Add application connection settings through environment variables and test
   reads before changing recognition to write to MySQL.

The SQL file only creates tables and records schema version 1. It does not
connect to a server, import the CSV, or alter the current attendance workflow.
