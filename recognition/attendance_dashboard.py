"""Generate an offline, read-only dashboard from the attendance CSV and roster."""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG = PROJECT_DIR / "attendance.csv"
DEFAULT_OUTPUT = PROJECT_DIR / "reports" / "attendance_dashboard.html"
DATASET_DIR = PROJECT_DIR / "dataset"


def load_dashboard_data(log_path):
    roster = sorted(path.name for path in DATASET_DIR.iterdir() if path.is_dir()) if DATASET_DIR.is_dir() else []
    if not roster:
        raise SystemExit(f"No student folders found in {DATASET_DIR}")
    if not log_path.is_file():
        raise SystemExit(f"Attendance log not found: {log_path}")

    attendance = {}
    with log_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "time", "student_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Attendance log is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            day = (row.get("date") or "").strip()
            time = (row.get("time") or "").strip()
            student_id = (row.get("student_id") or "").strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
                datetime.strptime(time, "%H:%M:%S")
            except ValueError:
                continue
            if student_id not in roster:
                continue
            attendance.setdefault(day, {})
            if student_id not in attendance[day] or time < attendance[day][student_id]:
                attendance[day][student_id] = time

    return {"roster": roster, "attendance": attendance, "dates": sorted(attendance, reverse=True)}


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Smart Attendance Dashboard</title>
  <style>
    :root { font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f3f6fb; }
    body { margin: 0; }
    header { background: #14243a; color: #fff; padding: 24px max(20px, calc((100% - 1100px)/2)); }
    header h1 { margin: 0 0 5px; font-size: 1.55rem; }
    header p { margin: 0; color: #c4d2e4; }
    main { max-width: 1100px; margin: 24px auto; padding: 0 18px 40px; }
    .controls { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
    select { padding: 9px 12px; border: 1px solid #c9d3e0; border-radius: 8px; background: white; font: inherit; }
    .cards { display: grid; grid-template-columns: repeat(4, minmax(130px,1fr)); gap: 14px; }
    .card, section { background: white; border: 1px solid #e1e7ef; border-radius: 12px; box-shadow: 0 3px 12px #15263a0a; }
    .card { padding: 16px; }
    .card span { display: block; color: #637188; font-size: .88rem; }
    .card strong { display: block; margin-top: 5px; font-size: 1.65rem; }
    section { margin-top: 18px; padding: 18px; overflow: hidden; }
    h2 { margin: 0 0 14px; font-size: 1.1rem; }
    .table-wrap { overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; min-width: 480px; }
    th, td { text-align: left; border-bottom: 1px solid #e8edf3; padding: 11px 9px; }
    th { color: #637188; font-size: .82rem; font-weight: 600; }
    .present { color: #087443; font-weight: 600; }
    .absent { color: #a54136; font-weight: 600; }
    .muted { color: #718096; }
    footer { margin-top: 18px; color: #718096; font-size: .82rem; }
    @media (max-width: 700px) { .cards { grid-template-columns: repeat(2, 1fr); } main { margin-top: 16px; } }
  </style>
</head>
<body>
  <header><h1>Smart Attendance</h1><p>Local read-only view of the attendance log</p></header>
  <main>
    <div class="controls"><label for="day">Attendance date</label><select id="day"></select></div>
    <div class="cards">
      <div class="card"><span>Present</span><strong id="present">0</strong></div>
      <div class="card"><span>Absent</span><strong id="absent">0</strong></div>
      <div class="card"><span>Roster size</span><strong id="roster">0</strong></div>
      <div class="card"><span>Attendance rate</span><strong id="rate">0%</strong></div>
    </div>
    <section><h2 id="daily-heading">Daily attendance</h2><div class="table-wrap"><table>
      <thead><tr><th>Student ID</th><th>Status</th><th>First check-in</th></tr></thead>
      <tbody id="daily"></tbody>
    </table></div></section>
    <section><h2>Recorded attendance by student</h2><div class="table-wrap"><table>
      <thead><tr><th>Student ID</th><th>Days present</th><th>Recorded dates</th></tr></thead>
      <tbody id="totals"></tbody>
    </table></div></section>
    <footer>Generated from the local CSV. This dashboard does not change attendance records. Verify attendance manually before relying on it.</footer>
  </main>
  <script>
    const data = __DATA__;
    const select = document.getElementById('day');
    const dailyBody = document.getElementById('daily');
    const totalsBody = document.getElementById('totals');
    const addCell = (row, value, className = '') => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (className) cell.className = className;
      row.appendChild(cell);
    };
    const option = document.createElement('option');
    option.value = 'all'; option.textContent = 'All dates'; select.appendChild(option);
    for (const day of data.dates) {
      const item = document.createElement('option');
      item.value = day; item.textContent = day; select.appendChild(item);
    }
    const render = () => {
      const day = select.value;
      const presentIds = day === 'all' ? new Set() : new Set(Object.keys(data.attendance[day] || {}));
      const present = day === 'all' ? null : presentIds.size;
      document.getElementById('present').textContent = day === 'all' ? '—' : present;
      document.getElementById('absent').textContent = day === 'all' ? '—' : data.roster.length - present;
      document.getElementById('roster').textContent = data.roster.length;
      document.getElementById('rate').textContent = day === 'all' ? '—' : `${data.roster.length ? Math.round(100 * present / data.roster.length) : 0}%`;
      document.getElementById('daily-heading').textContent = day === 'all' ? 'Select a date for daily attendance' : `Daily attendance · ${day}`;
      dailyBody.replaceChildren();
      if (day !== 'all') for (const id of data.roster) {
        const row = document.createElement('tr');
        const time = data.attendance[day]?.[id] || '';
        addCell(row, id);
        addCell(row, time ? 'Present' : 'Absent', time ? 'present' : 'absent');
        addCell(row, time || '—', time ? '' : 'muted');
        dailyBody.appendChild(row);
      }
      totalsBody.replaceChildren();
      for (const id of data.roster) {
        const days = data.dates.filter(date => data.attendance[date]?.[id]);
        const row = document.createElement('tr');
        addCell(row, id); addCell(row, String(days.length)); addCell(row, days.join(', ') || '—');
        totalsBody.appendChild(row);
      }
    };
    select.addEventListener('change', render);
    select.value = data.dates[0] || 'all';
    render();
  </script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_LOG, help="attendance CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="HTML output path")
    args = parser.parse_args()

    data = load_dashboard_data(args.input)
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = HTML_TEMPLATE.replace("__DATA__", payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Dashboard created: {args.output}")
    print(f"Roster: {len(data['roster'])} | Attendance dates: {len(data['dates'])}")


if __name__ == "__main__":
    main()
