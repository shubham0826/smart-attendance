# Smart Attendance System Through Camera

Camera-based attendance project. The current prototype captures student face
samples, creates face embeddings, recognizes enrolled students from a webcam,
records daily attendance, and exports a daily CSV report.

## Current setup

- OS: Windows
- Project environment: Python 3.13 in `.venv`
- Verified imports: OpenCV and NumPy
- Phase 1 image test passed; `phase1_test.png` was created
- Live webcam recognition and attendance logging have been run successfully
- Phase 2 frame helpers passed a synthetic-frame check; run the updated preview
  once to confirm its FPS overlay on the target camera
- Git repository initialized on `main`; the GitHub remote is configured

Use the project environment from any PowerShell location:

```powershell
& "C:\smart attendance\.venv\Scripts\Activate.ps1"
```

Run Phase 1's basic image check:

```powershell
python "C:\smart attendance\ai_module\phase1_test.py"
```

Run the camera preview:

```powershell
python "C:\smart attendance\ai_module\camera_test.py"
```

Press Q in the camera window to close it.

The Phase 2 preview resizes wide frames to 960 pixels, reports frame dimensions
and measured FPS, and keeps frames in OpenCV's BGR format for display. Use
`bgr_to_rgb()` before passing a frame to a library that expects RGB. The
`draw_bbox()` helper accepts `(left, top, right, bottom)` coordinates.

## Face detection (Phase 3)

The AI module uses OpenCV YuNet with the downloaded ONNX model in `models/`.
The model and its MIT license notice are stored together. Run the live detector:

```powershell
python "C:\smart attendance\ai_module\face_detection.py"
```

To check a single image without showing a window:

```powershell
python "C:\smart attendance\ai_module\face_detection.py" --image "C:\path\to\image.jpg" --no-display
```

To summarize results on the current enrollment photos:

```powershell
python "C:\smart attendance\ai_module\evaluate_face_detection.py"
python "C:\smart attendance\ai_module\compare_face_detectors.py"
```

The first evaluation scanned 80 images: YuNet found exactly one face in 69,
none in 11, and multiple faces in 0 at score thresholds 0.85, 0.65, and 0.50.
This set was captured using another detector and is not independently
annotated, so these numbers are a dataset sanity check, not accuracy results.
The detector still needs a separate test set covering different lighting and
viewing angles. The evaluation creates `reports/face_detection_review/review.csv`
and `reports/face_detection_review/contact_sheet.jpg`. All 11 missed images are
from one student's folder and show backgrounds rather than visible faces.
Recapture those samples with the camera aimed at the student before rebuilding
embeddings.
The comparison found exactly one face in 69/80 images with YuNet and 37/80
with the face-recognition HOG detector. Haar is unavailable in this OpenCV 5
build. These are coverage counts, not precision or accuracy scores, and the
enrollment images are not an independent test set.

## Recreate the Python environment

`requirements.txt` records the packages currently installed. On Windows x64
with Python 3.13, install that snapshot with:

```powershell
python -m pip install --no-deps -r "C:\smart attendance\requirements.txt"
```

`--no-deps` is needed because the prebuilt `dlib-bin` wheel supplies the `dlib`
module but its distribution name differs from the dependency declared by
`face-recognition`. The lock file lists the packages already installed in this
environment, including those dependencies.

## Existing prototype commands

From the active project environment:

```powershell
python "C:\smart attendance\recognition\enroll_student.py" STUDENT_ID_HERE
python "C:\smart attendance\recognition\create_embeddings.py"
python "C:\smart attendance\recognition\recognize.py"
python "C:\smart attendance\recognition\attendance_report.py"
python "C:\smart attendance\recognition\audit_attendance.py"
python "C:\smart attendance\recognition\attendance_dashboard.py"
python "C:\smart attendance\recognition\checkpoint_report.py"
```

With MySQL selected, each recognition run creates a class session and stores a
review-only checkpoint summary every 20 minutes. `checkpoint_report.py` exports
the latest session's records; pass `--session-id ID` to select another session.
Students not seen in a window are marked `not_observed` and remain pending human
review. This status does not establish absence.

The audit checks date/time fields, roster IDs, and duplicate daily check-ins.
It leaves the source log untouched and writes any flagged rows to
`reports/attendance_audit.csv`. The current two attendance rows passed with no
issues.

The dashboard command generates `reports/attendance_dashboard.html`, an offline
read-only page with a date selector, daily present/absent counts, check-in times,
and per-student attendance totals. Open that HTML file in a browser to view it;
it does not start a server or change the attendance log.

For a multi-day summary, specify an inclusive start and end date:

```powershell
python "C:\smart attendance\recognition\attendance_period_report.py" 2026-10-01 2026-10-31
```

The report is written as a separate CSV under `reports/`. Its denominator is the
number of dates in the selected range that contain at least one valid attendance
record; it does not assume weekends, holidays, or unrecorded class days.

To inspect identity separation without using a camera or adding attendance
records, run:

```powershell
python "C:\smart attendance\recognition\evaluate_matching.py"
```

This leave-one-out check uses the saved embeddings and writes a threshold sweep
to `reports/matching_evaluation/threshold_sweep.csv`. On the current 69 samples
across four IDs, it correctly matched all 69 at the recognizer's current 0.50
threshold. This is only an internal consistency check: the samples may include
near-duplicate frames from the same session, and no unknown-person samples were
tested. It does not validate the system for real attendance.

Enrollment opens the webcam; press Space to save each accepted sample and Q to
stop. The default target is 20 samples. It rejects frames unless exactly one
face at least 80 pixels wide is visible. The current embedding file was rebuilt
from 69 accepted samples across four students; the legacy file is backed up at
`reports/embedding_backups/face_embeddings_hog_backup_20261015.npz`. Enroll
students without samples before rebuilding embeddings again. Add correctly
captured face samples for folders containing background photos; these files are
ignored during embedding creation.

Embedding creation and attendance recognition now both use YuNet face boxes.
Embedding creation skips images with zero or multiple faces and writes a CSV
listing skipped files under `reports/embedding_rejections/`. The attendance
recognizer passes YuNet face boxes to the existing face-embedding matcher. Use
`--detector hog` to return to the legacy HOG detector, or adjust YuNet's
detection score threshold with `--score-threshold 0.65`. The existing matching
threshold is unchanged and still needs validation. Use
`python "C:\smart attendance\recognition\recognize.py" --help` to see the
available detector options.

Enrollment images, face embeddings, attendance logs, and generated reports are
local data and are excluded by `.gitignore`. Handle these biometric records
according to the project's consent, access, and retention requirements.

## Exam seat-plan groundwork

Use `exam/templates/seat_plan.template.json` as a starting point. Copy it to
`exam/seat_plan.local.json`, replace the placeholder exam and student IDs, and
calibrate each normalized seat-zone polygon against a frame from the intended
camera. Local plans are excluded from Git because they contain student-to-seat
assignments. Capture a local frame with `exam/capture_reference_frame.py`, then
use `exam/calibrate_seat_zones.py` with the private assignment CSV to draw the
polygons. Validate and inspect a still frame with:

```powershell
python "C:\smart attendance\exam\seat_plan.py" "C:\smart attendance\exam\seat_plan.local.json"
python "C:\smart attendance\exam\analyze_seat_image.py" --plan "C:\smart attendance\exam\seat_plan.local.json" --image "C:\path\to\test-frame.jpg" --no-display
```

The geometry-only still-image tool maps YuNet face-box centers to zones and
returns counts. `exam/analyze_exam_image.py` can also compare faces against the
local embeddings, using the attendance recognizer's experimental threshold.
Those matches are candidates for teacher review, not verified identities; a
possible mismatch is not a violation finding. Camera calibration and person
detection remain to be completed in the exam room. See `exam/README.md` for
details.

## Next phases

Phase 1 environment setup is complete. Phase 2 frame-processing helpers are
implemented and the webcam was already confirmed during live recognition. Phase
3 now uses YuNet; its current enrollment-set scan found 69 single-face
detections out of 80 images. Independent detection and robustness evaluation
remain. The current recognition code is a prototype; its matching threshold
has not been validated, and it must not be treated as an authoritative
attendance decision.
MySQL is supported as an optional attendance backend for recognition, daily and
period reports, dashboard generation, and review-only 20-minute checkpoints.
CSV remains the code default; the private local `.env` selects MySQL for this
machine. Checkpoint detections do not decide absence; missing detections remain
pending human review. See `database/README.md` for setup and reporting commands.
The institutional checkpoint policy and exam-seat verification remain future
work. A review-only seat-plan geometry foundation is in `exam/seat_plan.py`; it
does not identify students or make seating-violation decisions. Face matching
is still a prototype and needs independent validation.
